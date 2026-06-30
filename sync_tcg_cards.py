#!/usr/bin/env python3
"""
Pokemon TCG API -> Supabase card_catalog 数据同步脚本
按扩展包逐个拉取，支持稀有度过滤
"""

import json
import urllib.request
import urllib.parse
import time
import sys

# ============ 配置区 ============
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://your-project.supabase.co")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")
POKEMON_TCG_API = "https://api.pokemontcg.io/v2/cards"

# 剑/盾系列扩展包 (Sword & Shield)
SWORD_SHIELD_SETS = [
    "swsh1", "swsh2", "swsh3", "swsh35", "swsh4",
    "swsh45", "swsh45sv", "swsh5", "swsh6", "swsh7",
    "swsh8", "swsh9", "swsh9tg", "swsh10", "swsh10tg",
    "swsh11", "swsh11tg", "swsh12", "swsh12tg", "swsh12pt5", "swsh12pt5gg"
]

# 日/月系列扩展包 (Sun & Moon)
SUN_MOON_SETS = [
    "sm1", "sm2", "sm3", "sm35", "sm4",
    "sm5", "sm6", "sm7", "sm75", "sm8",
    "sm9", "sm10", "sm11", "sm115", "sma", "sm12"
]

# 当前要同步的扩展包（可切换）
ALL_SETS = SWORD_SHIELD_SETS + SUN_MOON_SETS  # 全部 37 个扩展包

# 稀有度过滤（空列表 = 拉取全部卡牌，不过滤）
POPULAR_RARITIES = []

PAGE_SIZE = 250
TEST_MODE = False
TEST_SETS = 2
# ============ 配置区结束 ============


def supabase_request(method, endpoint, data=None):
    url = f"{SUPABASE_URL}/rest/v1/{endpoint}"
    headers = {
        "apikey": SUPABASE_SERVICE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal"
    }
    if method == "GET" and data:
        url += "?" + urllib.parse.urlencode(data)
        req = urllib.request.Request(url, headers=headers)
    elif method == "POST":
        req = urllib.request.Request(url, data=json.dumps(data).encode(),
                                     headers={**headers, "Prefer": "return=representation"})
    else:
        req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        print(f"  ❌ Supabase HTTP {e.code}: {e.read().decode()}")
        return None
    except Exception as e:
        print(f"  ❌ Supabase 错误: {e}")
        return None


def fetch_tcg_cards(set_id, page):
    """拉取指定扩展包的卡牌（使用 q 参数）"""
    q = f'set.id:"{set_id}"'
    params = {"q": q, "page": page, "pageSize": PAGE_SIZE}
    url = f"{POKEMON_TCG_API}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url)
    req.add_header("User-Agent", "PokemonCardsManager/1.0")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None  # 扩展包不存在
        print(f"  ❌ TCG API HTTP {e.code}: {e.read().decode()}")
        return None
    except Exception as e:
        print(f"  ❌ TCG API 错误: {e}")
        return None


def get_existing_tcg_ids():
    print("📋 获取已有 tcg_id...")
    existing = set()
    offset = 0
    while True:
        result = supabase_request("GET", f"card_catalog?select=tcg_id&tcg_id=not.is.null&offset={offset}&limit=1000")
        if not result:
            break
        for r in result:
            if r.get("tcg_id"):
                existing.add(r["tcg_id"])
        if len(result) < 1000:
            break
        offset += 1000
    print(f"   已有 {len(existing)} 条")
    return existing


def convert_card(card, existing_ids):
    tcg_id = card.get("id", "")
    if tcg_id in existing_ids:
        return None
    # 稀有度过滤
    if POPULAR_RARITIES and card.get("rarity", "") not in POPULAR_RARITIES:
        return None

    prices = card.get("tcgplayer", {}).get("prices", {})
    market_price = 0
    for pt in ["holofoil", "reverseHolofoil", "normal", "unlimited"]:
        if pt in prices and prices[pt].get("market"):
            market_price = prices[pt]["market"]
            break

    def j(d):
        return json.dumps(d, ensure_ascii=False) if d is not None else None

    return {
        "name": card.get("name", ""),
        "name_en": card.get("name", ""),
        "set_name": card.get("set", {}).get("name", ""),
        "set_code": card.get("set", {}).get("id", ""),
        "card_number": card.get("number", ""),
        "rarity": card.get("rarity", ""),
        "image_url": card.get("images", {}).get("large", ""),
        "market_price": market_price,
        "category": "PTCG-EN",
        "language": "en",
        "tcg_id": tcg_id,
        "hp": int(card["hp"]) if str(card.get("hp", "")).isdigit() else None,
        "types": j(card.get("types")),
        "subtypes": j(card.get("subtypes")),
        "evolves_from": card.get("evolvesFrom"),
        "abilities": j(card.get("abilities")),
        "attacks": j(card.get("attacks")),
        "weaknesses": j(card.get("weaknesses")),
        "retreat_cost": card.get("convertedRetreatCost"),
        "artist": card.get("artist"),
        "flavor_text": card.get("flavorText"),
        "national_pokedex_numbers": j(card.get("nationalPokedexNumbers")),
        "legalities": j(card.get("legalities")),
    }


def batch_insert(rows):
    if not rows:
        return 0
    result = supabase_request("POST", "card_catalog", rows)
    return len(rows) if result is not None else 0


def sync_set(set_id, existing_ids):
    """拉取单个扩展包的所有卡牌"""
    print(f"\n📦 扩展包: {set_id}")
    page = 1
    inserted_total = 0
    skipped_total = 0

    while True:
        print(f"  第 {page} 页...", end=" ")
        data = fetch_tcg_cards(set_id, page)
        if not data or "data" not in data:
            print("无数据")
            break

        cards = data["data"]
        print(f"抓到 {len(cards)} 张")

        to_insert = []
        for c in cards:
            row = convert_card(c, existing_ids)
            if row:
                to_insert.append(row)
                existing_ids.add(row["tcg_id"])
            else:
                skipped_total += 1

        if to_insert:
            n = batch_insert(to_insert)
            inserted_total += n
            print(f"    ✅ 插入 {n} 条（累计 {inserted_total}）")

        # 下一页
        total = data.get("totalCount", 0)
        if page * PAGE_SIZE >= total:
            break
        page += 1
        time.sleep(0.3)

    print(f"  ✅ {set_id} 完成: 新增 {inserted_total}, 跳过 {skipped_total}")
    return inserted_total


def main():
    print("=" * 60)
    print("🚀 Pokemon TCG 数据同步脚本")
    print("=" * 60)

    sets_to_sync = ALL_SETS[:TEST_SETS] if TEST_MODE else ALL_SETS
    print(f"📊 待同步扩展包: {len(sets_to_sync)} 个")
    if POPULAR_RARITIES:
        print(f"📊 稀有度过滤: {len(POPULAR_RARITIES)} 种")
    else:
        print(f"📊 稀有度过滤: 无（拉取全部卡牌）")

    existing_ids = get_existing_tcg_ids()

    total_inserted = 0
    for i, set_id in enumerate(sets_to_sync, 1):
        print(f"\n[{i}/{len(sets_to_sync)}] ", end="")
        try:
            n = sync_set(set_id, existing_ids)
            total_inserted += n
        except Exception as e:
            print(f"  ❌ 扩展包 {set_id} 失败: {e}")

    print("\n" + "=" * 60)
    print(f"🎉 全部完成! 新增 {total_inserted} 条")
    print("=" * 60)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  用户中断")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 发生错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
