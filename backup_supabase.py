#!/usr/bin/env python3
"""
Supabase 数据备份脚本
导出所有表数据为本地 JSON 文件
"""

import json
import urllib.request
import urllib.parse
import os
from datetime import datetime

# ============ 配置区 ============
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://your-project.supabase.co")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")

# 备份文件保存目录
BACKUP_DIR = "backups"
# ============ 配置区结束 ============


def supabase_request(method, endpoint, params=None):
    """调用 Supabase REST API（GET）"""
    url = f"{SUPABASE_URL}/rest/v1/{endpoint}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    
    headers = {
        "apikey": SUPABASE_SERVICE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
    }
    req = urllib.request.Request(url, headers=headers)
    
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read())
    except Exception as e:
        print(f"  ❌ 导出失败: {e}")
        return None


def export_table(table_name, select_fields="*", order_by=None):
    """导出单个表的所有数据"""
    print(f"📦 导出 {table_name}...")
    
    params = {"select": select_fields, "limit": 1000}
    if order_by:
        params["order"] = order_by
    
    # 分页获取所有数据
    all_data = []
    offset = 0
    
    while True:
        params["offset"] = offset
        data = supabase_request("GET", table_name, params)
        
        if data is None:
            print(f"  ⚠️  请求失败，已导出 {len(all_data)} 条")
            break
        
        all_data.extend(data)
        
        if len(data) < 1000:
            break
        
        offset += 1000
        print(f"  已导出 {len(all_data)} 条...")
    
    print(f"  ✅ 导出 {len(all_data)} 条")
    return all_data


def save_json(data, filename):
    """保存为 JSON 文件"""
    path = os.path.join(BACKUP_DIR, filename)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"  💾 保存至 {path}")


def main():
    print("=" * 60)
    print("🗄️  Supabase 数据备份脚本")
    print("=" * 60)
    
    # 创建备份目录
    os.makedirs(BACKUP_DIR, exist_ok=True)
    print(f"📁 备份目录: {BACKUP_DIR}/")
    
    # 生成时间戳
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # 1. 导出 card_catalog（卡牌数据库）
    print("\n" + "-" * 60)
    catalog = export_table("card_catalog", order_by="id")
    if catalog:
        save_json(catalog, f"card_catalog_{timestamp}.json")
        # 同时保存一个 latest 版本（方便恢复）
        save_json(catalog, "card_catalog_latest.json")
    
    # 2. 导出 cards（用户卡牌仓库）
    print("\n" + "-" * 60)
    cards = export_table("cards", order_by="id")
    if cards:
        save_json(cards, f"cards_{timestamp}.json")
        save_json(cards, "cards_latest.json")
    
    # 3. 导出 price_records（价格记录）
    print("\n" + "-" * 60)
    prices = export_table("price_records", order_by="id")
    if prices:
        save_json(prices, f"price_records_{timestamp}.json")
        save_json(prices, "price_records_latest.json")
    
    # 4. 导出 profiles（用户资料）
    print("\n" + "-" * 60)
    profiles = export_table("profiles")
    if profiles:
        save_json(profiles, f"profiles_{timestamp}.json")
        save_json(profiles, "profiles_latest.json")
    
    # 5. 导出 snapshots（快照）
    print("\n" + "-" * 60)
    snapshots = export_table("snapshots", order_by="id")
    if snapshots:
        save_json(snapshots, f"snapshots_{timestamp}.json")
        save_json(snapshots, "snapshots_latest.json")
    
    # 生成汇总报告
    print("\n" + "=" * 60)
    print("🎉 备份完成!")
    print(f"📁 备份目录: {os.path.abspath(BACKUP_DIR)}/")
    print(f"📅 时间戳: {timestamp}")
    print("\n文件列表:")
    for f in os.listdir(BACKUP_DIR):
        if timestamp in f or f.endswith("_latest.json"):
            size = os.path.getsize(os.path.join(BACKUP_DIR, f)) / 1024
            print(f"  - {f} ({size:.1f} KB)")
    print("=" * 60)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  用户中断")
    except Exception as e:
        print(f"\n❌ 发生错误: {e}")
        import traceback
        traceback.print_exc()
