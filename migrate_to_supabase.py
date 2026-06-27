#!/usr/bin/env python3
"""
SQLite → Supabase 数据迁移脚本

用法:
  python migrate_to_supabase.py --url <SUPABASE_URL> --key <SUPABASE_SERVICE_KEY>

说明:
  - 读取本地 cards.db 的全部数据
  - 通过 Supabase REST API 批量写入 PostgreSQL
  - 自动创建 admin 用户（如果 Supabase Auth 中不存在）
  - 幂等：重复运行不会产生重复数据
"""

import argparse
import json
import sqlite3
import sys
import requests
import time

# ---- 增量提交辅助 ----
def chunked(seq, n):
    """将列表分成 n 个一组"""
    for i in range(0, len(seq), n):
        yield seq[i:i + n]


def supabase_insert(base_url, api_key, table, rows):
    """通过 Supabase REST API 批量插入，支持 upsert"""
    url = f"{base_url}/rest/v1/{table}"
    headers = {
        "apikey": api_key,
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Prefer": "return=representation,resolution=merge-duplicates",
    }
    # 批量提交（每批 50 条）
    total = 0
    for batch in chunked(rows, 50):
        resp = requests.post(url, headers=headers, json=batch, timeout=30)
        if resp.status_code not in (200, 201):
            print(f"  [ERROR] {table}: {resp.status_code} - {resp.text[:300]}")
            return -1
        total += len(batch)
    return total


def main():
    parser = argparse.ArgumentParser(description="Migrate SQLite to Supabase")
    parser.add_argument("--url", required=True, help="Supabase project URL (https://xxx.supabase.co)")
    parser.add_argument("--key", required=True, help="Supabase service_role key")
    parser.add_argument("--db", default="cards.db", help="SQLite database path")
    parser.add_argument("--admin-email", default="admin@kapai.local", help="Admin email for Supabase Auth")
    parser.add_argument("--admin-password", default="kapai2026", help="Admin password")
    args = parser.parse_args()

    base_url = args.url.rstrip("/")
    api_key = args.key

    print("=" * 60)
    print("  SQLite → Supabase 数据迁移")
    print("=" * 60)

    # ---- Step 1: Read SQLite ----
    print("\n[1/5] 读取 SQLite 数据...")
    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row

    catalog_rows = [dict(r) for r in conn.execute("SELECT * FROM card_catalog ORDER BY id").fetchall()]
    print(f"  card_catalog: {len(catalog_rows)} 条")

    card_rows = [dict(r) for r in conn.execute("SELECT * FROM cards ORDER BY id").fetchall()]
    print(f"  cards: {len(card_rows)} 条")

    price_rows = [dict(r) for r in conn.execute("SELECT * FROM price_records ORDER BY id").fetchall()]
    print(f"  price_records: {len(price_rows)} 条")

    snapshot_rows = [dict(r) for r in conn.execute("SELECT * FROM snapshots ORDER BY id").fetchall()]
    print(f"  snapshots: {len(snapshot_rows)} 条")

    user_rows = [dict(r) for r in conn.execute("SELECT * FROM users ORDER BY id").fetchall()]
    print(f"  users: {len(user_rows)} 条")
    conn.close()

    # ---- Step 2: Create admin user in Supabase Auth ----
    print("\n[2/5] 创建 admin 用户 (Supabase Auth)...")
    auth_url = f"{base_url}/auth/v1/admin/users"
    auth_headers = {
        "apikey": api_key,
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    # Check if admin user already exists
    resp = requests.get(f"{auth_url}?email={args.admin_email}", headers=auth_headers, timeout=10)
    admin_uuid = None
    if resp.status_code == 200:
        users_data = resp.json()
        if isinstance(users_data, list) and len(users_data) > 0:
            admin_uuid = users_data[0].get("id")
            print(f"  admin 用户已存在: {admin_uuid}")
        elif isinstance(users_data, dict) and "users" in users_data:
            for u in users_data["users"]:
                if u.get("email") == args.admin_email:
                    admin_uuid = u.get("id")
                    break
            if admin_uuid:
                print(f"  admin 用户已存在: {admin_uuid}")

    if not admin_uuid:
        # Create admin user
        payload = {
            "email": args.admin_email,
            "password": args.admin_password,
            "email_confirm": True,
            "user_metadata": {
                "username": "admin",
                "nick_name": "管理员",
                "role": "admin",
            }
        }
        resp = requests.post(auth_url, headers=auth_headers, json=payload, timeout=10)
        if resp.status_code in (200, 201):
            admin_uuid = resp.json().get("id")
            print(f"  admin 用户创建成功: {admin_uuid}")
        else:
            print(f"  [ERROR] 创建 admin 失败: {resp.status_code} - {resp.text[:300]}")
            sys.exit(1)

    # ---- Step 3: Update admin profile to admin role ----
    print("\n[3/5] 更新 admin profile...")
    profile_url = f"{base_url}/rest/v1/profiles?id=eq.{admin_uuid}"
    profile_data = {
        "id": admin_uuid,
        "username": "admin",
        "nick_name": "管理员",
        "role": "admin",
    }
    resp = requests.post(
        f"{base_url}/rest/v1/profiles",
        headers={
            "apikey": api_key,
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Prefer": "return=representation,resolution=merge-duplicates",
        },
        json=profile_data,
        timeout=10
    )
    if resp.status_code in (200, 201):
        print(f"  admin profile 更新成功")
    else:
        print(f"  [WARN] admin profile: {resp.status_code} - {resp.text[:200]}")

    # ---- Step 4: Migrate card_catalog ----
    print("\n[4/5] 迁移数据表...")

    # card_catalog
    catalog_payload = []
    for r in catalog_rows:
        catalog_payload.append({
            "id": r["id"],
            "name": r["name"],
            "name_en": r.get("name_en", ""),
            "set_name": r.get("set_name", ""),
            "set_code": r.get("set_code", ""),
            "card_number": r.get("card_number", ""),
            "rarity": r.get("rarity", ""),
            "image_url": r.get("image_url", ""),
            "description": r.get("description", ""),
            "market_price": r.get("market_price", 0) or 0,
            "category": r.get("category", "PTCG-SC"),
            "language": r.get("language", "zh"),
            "tcg_id": r.get("tcg_id", ""),
            "hp": r.get("hp"),
            "types": r.get("types"),
            "subtypes": r.get("subtypes"),
            "evolves_from": r.get("evolves_from"),
            "abilities": r.get("abilities"),
            "attacks": r.get("attacks"),
            "weaknesses": r.get("weaknesses"),
            "retreat_cost": r.get("retreat_cost"),
            "artist": r.get("artist"),
            "flavor_text": r.get("flavor_text"),
            "national_pokedex_numbers": r.get("national_pokedex_numbers"),
            "legalities": r.get("legalities"),
            "created_at": r.get("created_at"),
            "updated_at": r.get("updated_at"),
        })
    count = supabase_insert(base_url, api_key, "card_catalog", catalog_payload)
    print(f"  card_catalog: {count} 条迁移完成")

    # cards (use admin_uuid as user_id)
    cards_payload = []
    for r in card_rows:
        cards_payload.append({
            "id": r["id"],
            "user_id": admin_uuid,
            "catalog_id": r.get("catalog_id"),
            "name": r["name"],
            "name_en": r.get("name_en", ""),
            "set_name": r.get("set_name", ""),
            "card_number": r.get("card_number", ""),
            "rarity": r.get("rarity", "C"),
            "condition": r.get("condition", "NM"),
            "quantity": r.get("quantity", 1),
            "cost_price": r.get("cost_price", 0) or 0,
            "market_price": r.get("market_price", 0) or 0,
            "image_path": r.get("image_path", ""),
            "tcg_id": r.get("tcg_id", ""),
            "notes": r.get("notes", ""),
            "created_at": r.get("created_at"),
            "updated_at": r.get("updated_at"),
        })
    count = supabase_insert(base_url, api_key, "cards", cards_payload)
    print(f"  cards: {count} 条迁移完成")

    # price_records
    prices_payload = []
    for r in price_rows:
        prices_payload.append({
            "id": r["id"],
            "card_id": r.get("card_id"),
            "catalog_id": r.get("catalog_id"),
            "platform": r["platform"],
            "price": r["price"],
            "currency": r.get("currency", "CNY"),
            "recorded_at": r.get("recorded_at"),
        })
    count = supabase_insert(base_url, api_key, "price_records", prices_payload)
    print(f"  price_records: {count} 条迁移完成")

    # snapshots
    if snapshot_rows:
        snap_payload = []
        for r in snapshot_rows:
            snap_payload.append({
                "id": r["id"],
                "total_value": r.get("total_value", 0) or 0,
                "total_cost": r.get("total_cost", 0) or 0,
                "snapshot_date": r.get("snapshot_date"),
            })
        count = supabase_insert(base_url, api_key, "snapshots", snap_payload)
        print(f"  snapshots: {count} 条迁移完成")
    else:
        print("  snapshots: 0 条（跳过）")

    # ---- Step 5: Verify ----
    print("\n[5/5] 验证数据...")
    verify_headers = {"apikey": api_key, "Authorization": f"Bearer {api_key}"}
    for table in ("card_catalog", "cards", "price_records", "profiles", "snapshots"):
        resp = requests.get(
            f"{base_url}/rest/v1/{table}?select=id&limit=1",
            headers=verify_headers,
            timeout=10
        )
        count_resp = requests.get(
            f"{base_url}/rest/v1/{table}",
            headers={**verify_headers, "Prefer": "count=exact", "Range": "0-0"},
            timeout=10
        )
        total = count_resp.headers.get("content-range", "*/0").split("/")[-1]
        print(f"  {table}: {total} 条")

    print("\n" + "=" * 60)
    print("  迁移完成！")
    print("=" * 60)
    print(f"\n  Admin 账号: {args.admin_email}")
    print(f"  Admin 密码: {args.admin_password}")
    print(f"  Admin UUID: {admin_uuid}")
    print(f"\n  下一步: 在 supabase-config.js 中填入 Supabase URL 和 anon key")


if __name__ == "__main__":
    main()
