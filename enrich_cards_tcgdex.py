#!/usr/bin/env python3
"""
使用 tcgdex API 补充简体中文卡牌的详细信息和图片 URL。

策略：
1. 从 CrystMiku 数据中提取 pokedexCode（全国图鉴编号）
2. 下载 tcgdex 全量卡片列表（含 name/image）
3. 用 pokedexCode + hp + rarity 做多层匹配
4. 获取匹配卡片的详细数据（HP/攻击/弱点等）和图片 URL
5. 批量更新 Supabase
"""

import json
import os
import time
import requests

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://your-project.supabase.co")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")
SUPABASE_HEADERS = {
    "apikey": SUPABASE_SERVICE_KEY,
    "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
    "Content-Type": "application/json",
}

TCGDEX_API = "https://api.tcgdex.net/v2/en"
PROXY = "http://127.0.0.1:7897"

# ─── 缓存文件 ───
CACHE_DIR = os.path.expanduser("~/.cache/tcgdex")
os.makedirs(CACHE_DIR, exist_ok=True)

CRYSTM_FILE = os.path.expanduser("/Volumes/资料/workbuddy/kapai/ptcg_cards_chs.json")
CARD_LIST_FILE = os.path.join(CACHE_DIR, "card_list.json")
CARD_DETAIL_CACHE = os.path.join(CACHE_DIR, "card_details.json")
NAME_INDEX_FILE = os.path.join(CACHE_DIR, "name_index.json")


def fetch_tcgdex(path, use_cache=True):
    """通用 tcgdex API 请求，支持代理和缓存"""
    url = f"{TCGDEX_API}/{path}"

    # 缓存检查
    cache_file = os.path.join(CACHE_DIR, path.replace("/", "_") + ".json")
    if use_cache and os.path.exists(cache_file):
        with open(cache_file) as f:
            return json.load(f)

    try:
        resp = requests.get(url, proxies={"http": PROXY, "https": PROXY}, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        with open(cache_file, "w") as f:
            json.dump(data, f, ensure_ascii=False)
        return data
    except Exception as e:
        print(f"  ⚠️ {url}: {e}")
        return None


# ═══════════════════════════════════════════════════
#  STEP 1: 下载 tcgdex 全量卡片列表并建立索引
# ═══════════════════════════════════════════════════
def build_card_list():
    """下载 tcgdex 卡片列表（含 name/image），建立按名称索引"""
    print("📥 下载 tcgdex 卡片列表...")
    cards = fetch_tcgdex("cards")
    if not cards:
        print("❌ 下载失败")
        return None
    print(f"   ✅ {len(cards)} 张卡片")

    # 建立索引：name → [card_summary]
    name_index = {}
    for c in cards:
        name = c.get("name", "").lower()
        if name not in name_index:
            name_index[name] = []
        name_index[name].append(c)

    with open(NAME_INDEX_FILE, "w") as f:
        json.dump(name_index, f, ensure_ascii=False)

    # 也保存原始列表
    with open(CARD_LIST_FILE, "w") as f:
        json.dump(cards, f, ensure_ascii=False)

    print(f"   📊 建立名称索引: {len(name_index)} 个唯一名称")
    return name_index


# ═══════════════════════════════════════════════════
#  STEP 2: 用全国图鉴编号匹配卡片
# ═══════════════════════════════════════════════════
def build_dex_index(card_list):
    """从 tcgdex 卡片详细数据建立 dexId → [cards] 索引"""
    # 加载缓存的详细数据
    details = {}
    if os.path.exists(CARD_DETAIL_CACHE):
        with open(CARD_DETAIL_CACHE) as f:
            details = json.load(f)
        print(f"   📂 已缓存 {len(details)} 张卡片详细数据")

    # 需要获取详细数据的卡片（只获取需要的）
    # 先分析 CrystMiku 数据中出现的所有 pokedexCode
    with open(CRYSTM_FILE, "r", encoding="utf-8") as f:
        chs_data = json.load(f)

    needed_dexes = set()
    for s in chs_data:
        for c in s.get("cards", []):
            dex = c.get("details", {}).get("pokedexCode")
            if dex:
                needed_dexes.add(dex)

    print(f"   🔍 CrystMiku 数据中涉及 {len(needed_dexes)} 个不同的宝可梦图鉴编号")

    # 建立 dexId → [card_ids] 索引（先粗略索引，后续精确匹配）
    dex_index = {}

    # 检查是否已有索引
    dex_index_file = os.path.join(CACHE_DIR, "dex_index.json")
    if os.path.exists(dex_index_file):
        with open(dex_index_file) as f:
            dex_index = json.load(f)
        print(f"   📂 已缓存 dexId 索引: {len(dex_index)} 个图鉴编号")
        return dex_index

    # 需要获取每张卡片的详细数据来获得 dexId
    # 策略：先从 name_index 中用宝可梦名称匹配，获取候选卡片 ID
    # 然后批量获取详细数据

    # 先读取名称索引
    if not os.path.exists(NAME_INDEX_FILE):
        print("   ⚠️ 名称索引不存在，先建立...")
        build_card_list()

    with open(NAME_INDEX_FILE) as f:
        name_index = json.load(f)

    # 用 CrystMiku 的宝可梦名称匹配
    # 建立中文名→英文名映射（通过 pokedexCode 精确匹配）
    pokemon_names = {
        1: "Bulbasaur", 2: "Ivysaur", 3: "Venusaur",
        4: "Charmander", 5: "Charmeleon", 6: "Charizard",
        7: "Squirtle", 8: "Wartortle", 9: "Blastoise",
        10: "Caterpie", 11: "Metapod", 12: "Butterfree",
        13: "Weedle", 14: "Kakuna", 15: "Beedrill",
        16: "Pidgey", 17: "Pidgeotto", 18: "Pidgeot",
        19: "Rattata", 20: "Raticate",
        21: "Spearow", 22: "Fearow",
        23: "Ekans", 24: "Arbok",
        25: "Pikachu", 26: "Raichu",
        27: "Sandshrew", 28: "Sandslash",
        29: "Nidoran♀", 30: "Nidorina", 31: "Nidoqueen",
        32: "Nidoran♂", 33: "Nidorino", 34: "Nidoking",
        35: "Clefairy", 36: "Clefable",
        37: "Vulpix", 38: "Ninetales",
        39: "Jigglypuff", 40: "Wigglytuff",
        41: "Zubat", 42: "Golbat",
        43: "Oddish", 44: "Gloom", 45: "Vileplume",
        46: "Paras", 47: "Parasect",
        48: "Venonat", 49: "Venomoth",
        50: "Diglett", 51: "Dugtrio",
        52: "Meowth", 53: "Persian",
        54: "Psyduck", 55: "Golduck",
        56: "Mankey", 57: "Primeape",
        58: "Growlithe", 59: "Arcanine",
        60: "Poliwag", 61: "Poliwhirl", 62: "Poliwrath",
        63: "Abra", 64: "Kadabra", 65: "Alakazam",
        66: "Machop", 67: "Machoke", 68: "Machamp",
        69: "Bellsprout", 70: "Weepinbell", 71: "Victreebel",
        72: "Tentacool", 73: "Tentacruel",
        74: "Geodude", 75: "Graveler", 76: "Golem",
        77: "Ponyta", 78: "Rapidash",
        79: "Slowpoke", 80: "Slowbro",
        81: "Magnemite", 82: "Magneton",
        83: "Farfetch'd",
        84: "Doduo", 85: "Dodrio",
        86: "Seel", 87: "Dewgong",
        88: "Grimer", 89: "Muk",
        90: "Shellder", 91: "Cloyster",
        92: "Gastly", 93: "Haunter", 94: "Gengar",
        95: "Onix",
        96: "Drowzee", 97: "Hypno",
        98: "Krabby", 99: "Kingler",
        100: "Voltorb", 101: "Electrode",
        102: "Exeggcute", 103: "Exeggutor",
        104: "Cubone", 105: "Marowak",
        106: "Hitmonlee", 107: "Hitmonchan",
        108: "Lickitung",
        109: "Koffing", 110: "Weezing",
        111: "Rhyhorn", 112: "Rhydon",
        113: "Chansey",
        114: "Tangela",
        115: "Kangaskhan",
        116: "Horsea", 117: "Seadra",
        118: "Goldeen", 119: "Seaking",
        120: "Staryu", 121: "Starmie",
        122: "Mr. Mime",
        123: "Scyther",
        124: "Jynx",
        125: "Electabuzz",
        126: "Magmar",
        127: "Pinsir",
        128: "Tauros",
        129: "Magikarp", 130: "Gyarados",
        131: "Lapras",
        132: "Ditto",
        133: "Eevee", 134: "Vaporeon", 135: "Jolteon", 136: "Flareon",
        137: "Porygon",
        138: "Omanyte", 139: "Omastar",
        140: "Kabuto", 141: "Kabutops",
        142: "Aerodactyl",
        143: "Snorlax",
        144: "Articuno", 145: "Zapdos", 146: "Moltres",
        147: "Dratini", 148: "Dragonair", 149: "Dragonite",
        150: "Mewtwo", 151: "Mew",
    }

    print("   🔄 获取卡片详细数据建立 dexId 索引...")
    # 批量处理：先收集需要查找的卡片
    # 只获取 CrystMiku 中涉及的宝可梦对应的 tcgdex 卡片

    all_card_ids_to_fetch = set()
    for dex in needed_dexes:
        if dex in pokemon_names:
            en_name = pokemon_names[dex].lower()
            candidates = name_index.get(en_name, [])
            for cand in candidates:
                all_card_ids_to_fetch.add(cand["id"])

    print(f"   📋 需要获取详细数据的卡片: {len(all_card_ids_to_fetch)} 张")

    # 批量获取详细数据
    fetched = 0
    for card_id in all_card_ids_to_fetch:
        if card_id in details:
            continue

        detail = fetch_tcgdex(f"cards/{card_id}")
        if detail:
            details[card_id] = detail
            fetched += 1
            if fetched % 100 == 0:
                print(f"      已获取 {fetched} 张...")
                # 定期保存
                with open(CARD_DETAIL_CACHE, "w") as f:
                    json.dump(details, f, ensure_ascii=False)
        time.sleep(0.1)  # 限速

    # 最终保存
    with open(CARD_DETAIL_CACHE, "w") as f:
        json.dump(details, f, ensure_ascii=False)

    # 建立 dexId 索引
    for card_id, detail in details.items():
        for dex in detail.get("dexId", []):
            if dex not in dex_index:
                dex_index[dex] = []
            dex_index[dex].append(card_id)

    # 保存索引
    with open(dex_index_file, "w") as f:
        json.dump(dex_index, f, ensure_ascii=False)

    print(f"   ✅ dexId 索引建立完成: {len(dex_index)} 个图鉴编号, {len(details)} 张卡片详情")
    return dex_index


# ═══════════════════════════════════════════════════
#  STEP 3: 匹配卡片
# ═══════════════════════════════════════════════════
def match_card(card_zh, dex_index, details_cache, name_index):
    """匹配一张 CrystMiku 卡牌到 tcgdex 卡片"""
    details = card_zh.get("details", {})
    pokedex_code = details.get("pokedexCode")
    hp = details.get("hp")
    rarity_text = details.get("rarityText")
    illustrator = (details.get("illustratorName") or [None])[0]
    card_name_cn = details.get("cardName", "")
    card_number = details.get("collectionNumber", "001/001")

    best_match = None
    best_score = 0

    # 方法1: 用 pokedexCode 匹配
    if pokedex_code and pokedex_code in dex_index:
        candidates = dex_index[pokedex_code]

        for card_id in candidates:
            detail = details_cache.get(card_id, {})
            if not detail:
                continue

            score = 0

            # HP 匹配（高权重）
            tcg_hp = detail.get("hp")
            if tcg_hp and hp and tcg_hp == hp:
                score += 30

            # 稀有度匹配
            tcg_rarity = detail.get("rarity", "").lower()
            if rarity_text:
                rarity_map = {
                    "C": "common", "U": "uncommon", "R": "rare",
                    "RR": "rare", "SR": "rare", "SAR": "rare",
                    "UR": "rare", "HR": "rare", "CSR": "rare",
                }
                mapped = rarity_map.get(rarity_text, "").lower()
                if mapped and mapped in tcg_rarity:
                    score += 15

            # 画师匹配
            tcg_illustrator = detail.get("illustrator", "")
            if illustrator and tcg_illustrator and (
                illustrator.lower() in tcg_illustrator.lower()
                or tcg_illustrator.lower() in illustrator.lower()
            ):
                score += 20

            # 名称相似度（用卡牌名后半段）
            tcg_name = detail.get("name", "")
            if tcg_name:
                # 检查是否是同一进化阶段
                tcg_stage = detail.get("stage", "")
                if "V-UNION" in card_name_cn or "VMAX" in card_name_cn or "VSTAR" in card_name_cn:
                    # 特殊卡，尽量匹配
                    if tcg_name.endswith(" VMAX") or tcg_name.endswith(" VSTAR") or tcg_name.endswith(" V-UNION"):
                        score += 10
                elif tcg_stage == "Basic":
                    if "基础" in details.get("evolveText", ""):
                        score += 5
                elif tcg_stage == "Stage 1":
                    if "1阶进化" in details.get("evolveText", ""):
                        score += 5
                elif tcg_stage == "Stage 2":
                    if "2阶进化" in details.get("evolveText", ""):
                        score += 5

            # 匹配 set（用 set 发布日期）
            # 这里先跳过，set 映射较复杂

            if score > best_score:
                best_score = score
                best_match = card_id

    # 方法2: 用名称模糊匹配（当 pokedexCode 匹配不到时）
    if not best_match and card_name_cn:
        # 尝试从中文名中提取关键词
        # 简化处理：移除常见后缀
        keywords = card_name_cn
        for suffix in ["VMAX", "VSTAR", "V-UNION", "GX", "ex", "V", "LV.X"]:
            keywords = keywords.replace(suffix, "")
        keywords = keywords.strip()

        # 在名称索引中搜索
        for name, cards in name_index.items():
            if keywords.lower() in name.lower():
                for c in cards:
                    card_id = c["id"]
                    if card_id in details_cache:
                        detail = details_cache[card_id]
                        if detail.get("hp") == hp:
                            best_match = card_id
                            best_score = 15
                            break
                if best_match:
                    break

    return best_match, best_score


# ═══════════════════════════════════════════════════
#  STEP 4: 更新 Supabase
# ═══════════════════════════════════════════════════
def update_supabase_card(tcg_id, updates):
    """更新 Supabase 中的一条卡牌记录"""
    try:
        resp = requests.patch(
            f"{SUPABASE_URL}/rest/v1/card_catalog",
            headers={**SUPABASE_HEADERS, "Prefer": "return=minimal"},
            params={"tcg_id": f"eq.{tcg_id}"},
            json=updates,
            timeout=15,
        )
        return resp.status_code in (200, 204)
    except Exception as e:
        print(f"    ❌ 更新 {tcg_id} 失败: {e}")
        return False


# ═══════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════
def main():
    print("=" * 60)
    print("🃏 宝可梦卡牌数据补充脚本 (tcgdex)")
    print("=" * 60)

    # Step 1: 准备索引
    print("\n[1/4] 准备 tcgdex 索引...")
    name_index = build_card_list()
    if not name_index:
        return

    # 加载详细数据缓存
    if os.path.exists(CARD_DETAIL_CACHE):
        with open(CARD_DETAIL_CACHE) as f:
            details_cache = json.load(f)
    else:
        details_cache = {}

    dex_index = build_dex_index(None)  # 会从文件读取或新建

    # Step 2: 加载 CrystMiku 数据
    print("\n[2/4] 加载 CrystMiku 数据...")
    with open(CRYSTM_FILE, "r", encoding="utf-8") as f:
        chs_data = json.load(f)

    total_cards = sum(len(s.get("cards", [])) for s in chs_data)
    print(f"   ✅ {len(chs_data)} 个卡包, {total_cards} 张卡牌")

    # Step 3: 匹配并更新
    print("\n[3/4] 开始匹配和更新...")
    matched = 0
    unmatched = 0
    updated = 0
    failed_update = 0

    for set_idx, s in enumerate(chs_data):
        set_name = s.get("name", "Unknown")
        set_code = s.get("commodityCode", "Unknown")

        for card in s.get("cards", []):
            details = card.get("details", {})
            card_name = details.get("cardName", "Unknown")
            card_num = details.get("collectionNumber", "???")

            # 构建 tcg_id（与导入脚本一致）
            tcg_id = f"PTCG-{s['id']}-{card['id']}"

            # 匹配
            match_id, score = match_card(card, dex_index, details_cache, name_index)

            if match_id and score >= 15:
                matched += 1
                match_detail = details_cache.get(match_id, {})

                # 准备更新字段
                updates = {}

                # 图片 URL
                if match_detail.get("image"):
                    image_url = match_detail["image"]
                    # tcgdex 返回的是不带扩展名的 URL，加 .png
                    if not image_url.startswith("http"):
                        image_url = f"https://assets.tcgdex.net{image_url}"
                    updates["image_url"] = image_url + ".png"

                # 英文名
                if match_detail.get("name"):
                    updates["name_en"] = match_detail["name"]

                # HP
                if match_detail.get("hp"):
                    updates["hp"] = match_detail["hp"]

                # 属性
                if match_detail.get("types"):
                    updates["types"] = match_detail["types"]

                # 画师
                if match_detail.get("illustrator"):
                    updates["artist"] = match_detail["illustrator"]

                # 更新
                if updates:
                    success = update_supabase_card(tcg_id, updates)
                    if success:
                        updated += 1
                    else:
                        failed_update += 1

                if matched % 500 == 0:
                    print(f"   已匹配 {matched}/{total_cards} ({matched/total_cards*100:.1f}%), 已更新 {updated}")
            else:
                unmatched += 1

            # 进度显示
            total_processed = matched + unmatched
            if total_processed % 1000 == 0:
                print(f"   进度: {total_processed}/{total_cards} ({total_processed/total_cards*100:.1f}%), 匹配={matched}, 未匹配={unmatched}")

    # Step 4: 总结
    print(f"\n[4/4] 完成！")
    print(f"   ✅ 匹配成功: {matched}")
    print(f"   ⚠️ 未匹配: {unmatched}")
    print(f"   📤 已更新: {updated}")
    print(f"   ❌ 更新失败: {failed_update}")
    print(f"   📊 匹配率: {matched/total_cards*100:.1f}%")

    # 验证：查询更新后的数据
    print("\n验证更新结果：")
    resp = requests.get(
        f"{SUPABASE_URL}/rest/v1/card_catalog",
        headers={**SUPABASE_HEADERS, "Prefer": "count=exact"},
        params={"select": "id,image_url", "language": "eq.zh", "limit": 5, "image_url": "not.is.null"},
        timeout=15,
    )
    print(f"   有图片的简体中文卡牌: {resp.headers.get('Content-Range', 'N/A')}")


if __name__ == "__main__":
    main()
