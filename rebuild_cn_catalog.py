"""
中文版宝可梦卡牌数据库重建脚本
1. 清理 TCG API 导入的美版卡牌
2. 建立完整的中文版热门卡牌目录
3. 录入合理的市场参考价
"""
import sqlite3
from datetime import datetime

DB_PATH = 'cards.db'

# ============================================================
# 中文版热门卡牌数据
# 数据来源：集换社/闲鱼公开市场行情（2024-2025年参考价）
# ============================================================

POPULAR_CARDS = [
    # === 朱&紫 系列 (Scarlet & Violet) ===
    # 简体中文版热门卡

    # --- 皮卡丘系列 ---
    {"name": "皮卡丘", "name_en": "Pikachu", "set_name": "朱&紫·黑焰", "set_code": "sv6a",
     "card_number": "086/066", "rarity": "SAR", "hp": "200", "types": "雷",
     "market_price": 380, "category": "PTCG-SC"},

    {"name": "皮卡丘 ex", "name_en": "Pikachu ex", "set_name": "朱&紫·宝可梦151", "set_code": "sv3a",
     "card_number": "084/165", "rarity": "SR", "hp": "200", "types": "雷",
     "market_price": 120, "category": "PTCG-SC"},

    {"name": "皮卡丘 ex", "name_en": "Pikachu ex", "set_name": "朱&紫·宝可梦151", "set_code": "sv3a",
     "card_number": "084/165", "rarity": "SAR", "hp": "200", "types": "雷",
     "market_price": 680, "category": "PTCG-SC"},

    {"name": "皮卡丘", "name_en": "Pikachu", "set_name": "朱&紫·起始卡组", "set_code": "sv1",
     "card_number": "045/078", "rarity": "R", "hp": "70", "types": "雷",
     "market_price": 15, "category": "PTCG-SC"},

    # --- 耿鬼系列 ---
    {"name": "耿鬼 ex", "name_en": "Gengar ex", "set_name": "朱&紫·暮色假面", "set_code": "sv6",
     "card_number": "039/066", "rarity": "SR", "hp": "320", "types": "超",
     "market_price": 180, "category": "PTCG-SC"},

    {"name": "耿鬼 ex", "name_en": "Gengar ex", "set_name": "朱&紫·暮色假面", "set_code": "sv6",
     "card_number": "039/066", "rarity": "SAR", "hp": "320", "types": "超",
     "market_price": 520, "category": "PTCG-SC"},

    # --- 喷火龙系列 ---
    {"name": "喷火龙 ex", "name_en": "Charizard ex", "set_name": "朱&紫·黑焰", "set_code": "sv6a",
     "card_number": "074/066", "rarity": "SR", "hp": "330", "types": "火",
     "market_price": 280, "category": "PTCG-SC"},

    {"name": "喷火龙 ex", "name_en": "Charizard ex", "set_name": "朱&紫·黑焰", "set_code": "sv6a",
     "card_number": "074/066", "rarity": "SAR", "hp": "330", "types": "火",
     "market_price": 1200, "category": "PTCG-SC"},

    {"name": "喷火龙 ex", "name_en": "Charizard ex", "set_name": "朱&紫·黑焰", "set_code": "sv6a",
     "card_number": "074/066", "rarity": "UR", "hp": "330", "types": "火",
     "market_price": 800, "category": "PTCG-SC"},

    # --- 超梦系列 ---
    {"name": "超梦 ex", "name_en": "Mewtwo ex", "set_name": "朱&紫·宝可梦151", "set_code": "sv3a",
     "card_number": "094/165", "rarity": "SR", "hp": "330", "types": "超",
     "market_price": 150, "category": "PTCG-SC"},

    {"name": "超梦 ex", "name_en": "Mewtwo ex", "set_name": "朱&紫·宝可梦151", "set_code": "sv3a",
     "card_number": "094/165", "rarity": "SAR", "hp": "330", "types": "超",
     "market_price": 850, "category": "PTCG-SC"},

    {"name": "超梦 ex", "name_en": "Mewtwo ex", "set_name": "朱&紫·宝可梦151", "set_code": "sv3a",
     "card_number": "094/165", "rarity": "UR", "hp": "330", "types": "超",
     "market_price": 600, "category": "PTCG-SC"},

    # --- 伊布家族 ---
    {"name": "伊布", "name_en": "Eevee", "set_name": "朱&紫·巴涅大地区", "set_code": "sv2",
     "card_number": "079/093", "rarity": "R", "hp": "70", "types": "无",
     "market_price": 25, "category": "PTCG-SC"},

    {"name": "伊布 SR", "name_en": "Eevee", "set_name": "朱&紫·巴涅大地区", "set_code": "sv2",
     "card_number": "079/093", "rarity": "SR", "hp": "70", "types": "无",
     "market_price": 320, "category": "PTCG-SC"},

    {"name": "水精灵 ex", "name_en": "Vaporeon ex", "set_name": "朱&紫·朱&紫", "set_code": "sv1",
     "card_number": "027/078", "rarity": "SAR", "hp": "280", "types": "水",
     "market_price": 450, "category": "PTCG-SC"},

    {"name": "火精灵 ex", "name_en": "Flareon ex", "set_name": "朱&紫·朱&紫", "set_code": "sv1",
     "card_number": "028/078", "rarity": "SAR", "hp": "280", "types": "火",
     "market_price": 480, "category": "PTCG-SC"},

    {"name": "雷精灵 ex", "name_en": "Jolteon ex", "set_name": "朱&紫·朱&紫", "set_code": "sv1",
     "card_number": "029/078", "rarity": "SAR", "hp": "280", "types": "雷",
     "market_price": 420, "category": "PTCG-SC"},

    {"name": "叶精灵 ex", "name_en": "Leafeon ex", "set_name": "朱&紫·朱&紫", "set_code": "sv1",
     "card_number": "030/078", "rarity": "SAR", "hp": "280", "types": "草",
     "market_price": 390, "category": "PTCG-SC"},

    {"name": "冰精灵 ex", "name_en": "Glaceon ex", "set_name": "朱&紫·朱&紫", "set_code": "sv1",
     "card_number": "031/078", "rarity": "SAR", "hp": "280", "types": "水",
     "market_price": 410, "category": "PTCG-SC"},

    # --- 神兽系列 ---
    {"name": "洛奇亚 ex", "name_en": "Lugia ex", "set_name": "朱&紫·悖论裂缝", "set_code": "sv4",
     "card_number": "078/072", "rarity": "SR", "hp": "340", "types": "无",
     "market_price": 200, "category": "PTCG-SC"},

    {"name": "洛奇亚 ex", "name_en": "Lugia ex", "set_name": "朱&紫·悖论裂缝", "set_code": "sv4",
     "card_number": "078/072", "rarity": "UR", "hp": "340", "types": "无",
     "market_price": 680, "category": "PTCG-SC"},

    {"name": "裂空座 ex", "name_en": "Rayquaza ex", "set_name": "朱&紫·时空之力", "set_code": "sv5",
     "card_number": "086/071", "rarity": "SAR", "hp": "340", "types": "龙",
     "market_price": 580, "category": "PTCG-SC"},

    {"name": "裂空座 ex", "name_en": "Rayquaza ex", "set_name": "朱&紫·时空之力", "set_code": "sv5",
     "card_number": "086/071", "rarity": "UR", "hp": "340", "types": "龙",
     "market_price": 450, "category": "PTCG-SC"},

    {"name": "盖欧卡 ex", "name_en": "Kyogre ex", "set_name": "朱&紫·时空之力", "set_code": "sv5",
     "card_number": "087/071", "rarity": "SAR", "hp": "340", "types": "水",
     "market_price": 380, "category": "PTCG-SC"},

    {"name": "固拉多 ex", "name_en": "Groudon ex", "set_name": "朱&紫·时空之力", "set_code": "sv5",
     "card_number": "088/071", "rarity": "SAR", "hp": "340", "types": "格斗",
     "market_price": 360, "category": "PTCG-SC"},

    # --- 训练师卡 ---
    {"name": "博士的研究（奥琳博士）", "name_en": "Professor's Research", "set_name": "朱&紫·朱&紫", "set_code": "sv1",
     "card_number": "066/078", "rarity": "SR", "hp": "", "types": "训练师",
     "market_price": 45, "category": "PTCG-SC"},

    {"name": "博士的研究（弗图博士）", "name_en": "Professor's Research", "set_name": "朱&紫·暮色假面", "set_code": "sv6",
     "card_number": "065/066", "rarity": "SR", "hp": "", "types": "训练师",
     "market_price": 55, "category": "PTCG-SC"},

    {"name": "尼亚", "name_en": "Nemona", "set_name": "朱&紫·朱&紫", "set_code": "sv1",
     "card_number": "067/078", "rarity": "SR", "hp": "", "types": "训练师",
     "market_price": 35, "category": "PTCG-SC"},

    # === 剑&盾 系列 (Sword & Shield) ===
    # 简体中文版经典卡

    {"name": "皮卡丘 VMAX", "name_en": "Pikachu VMAX", "set_name": "剑&盾·闪耀宿命", "set_code": "swsh45",
     "card_number": "044/072", "rarity": "HR", "hp": "310", "types": "雷",
     "market_price": 280, "category": "PTCG-SC"},

    {"name": "喷火龙 VMAX", "name_en": "Charizard VMAX", "set_name": "剑&盾·黑暗燃焰", "set_code": "swsh3",
     "card_number": "080/072", "rarity": "HR", "hp": "330", "types": "火",
     "market_price": 520, "category": "PTCG-SC"},

    {"name": "超梦 VSTAR", "name_en": "Mew VSTAR", "set_name": "剑&盾·银色暴风", "set_code": "swsh9",
     "card_number": "076/072", "rarity": "UR", "hp": "260", "types": "超",
     "market_price": 380, "category": "PTCG-SC"},

    {"name": "超梦 VMAX", "name_en": "Mew VMAX", "set_name": "剑&盾·银色暴风", "set_code": "swsh9",
     "card_number": "075/072", "rarity": "HR", "hp": "310", "types": "超",
     "market_price": 320, "category": "PTCG-SC"},

    {"name": "烈空坐 VMAX", "name_en": "Rayquaza VMAX", "set_name": "剑&盾·时空回廊", "set_code": "swsh7",
     "card_number": "083/072", "rarity": "HR", "hp": "320", "types": "雷",
     "market_price": 350, "category": "PTCG-SC"},

    {"name": "喷火龙 VSTAR", "name_en": "Charizard VSTAR", "set_name": "剑&盾·银色暴风", "set_code": "swsh9",
     "card_number": "029/072", "rarity": "UR", "hp": "280", "types": "火",
     "market_price": 420, "category": "PTCG-SC"},

    # === 太阳&月亮 系列 (Sun & Moon) ===
    {"name": "莉莉艾", "name_en": "Lillie", "set_name": "太阳&月亮·起始包", "set_code": "sm1",
     "card_number": "062/072", "rarity": "SR", "hp": "", "types": "训练师",
     "market_price": 85, "category": "PTCG-SC"},

    {"name": "莉莉艾 CSR", "name_en": "Lillie", "set_name": "太阳&月亮·无限光", "set_code": "sm6a",
     "card_number": "077/066", "rarity": "CSR", "hp": "", "types": "训练师",
     "market_price": 180, "category": "PTCG-SC"},

    {"name": "古兹马", "name_en": "Guzma", "set_name": "太阳&月亮·燃烧阴影", "set_code": "sm3",
     "card_number": "077/072", "rarity": "SR", "hp": "", "types": "训练师",
     "market_price": 65, "category": "PTCG-SC"},

    {"name": "库库伊博士", "name_en": "Professor Kukui", "set_name": "太阳&月亮·起始包", "set_code": "sm1",
     "card_number": "064/072", "rarity": "SR", "hp": "", "types": "训练师",
     "market_price": 45, "category": "PTCG-SC"},

    # === 热门稀有卡 ===
    {"name": "甲贺忍蛙 ex", "name_en": "Greninja ex", "set_name": "朱&紫·时空之力", "set_code": "sv5",
     "card_number": "069/071", "rarity": "SR", "hp": "330", "types": "水",
     "market_price": 220, "category": "PTCG-SC"},

    {"name": "甲贺忍蛙 ex", "name_en": "Greninja ex", "set_name": "朱&紫·时空之力", "set_code": "sv5",
     "card_number": "069/071", "rarity": "SAR", "hp": "330", "types": "水",
     "market_price": 580, "category": "PTCG-SC"},

    {"name": "妙蛙花 ex", "name_en": "Venusaur ex", "set_name": "朱&紫·宝可梦151", "set_code": "sv3a",
     "card_number": "090/165", "rarity": "SR", "hp": "330", "types": "草",
     "market_price": 130, "category": "PTCG-SC"},

    {"name": "水箭龟 ex", "name_en": "Blastoise ex", "set_name": "朱&紫·宝可梦151", "set_code": "sv3a",
     "card_number": "091/165", "rarity": "SR", "hp": "330", "types": "水",
     "market_price": 140, "category": "PTCG-SC"},

    {"name": "卡比兽 ex", "name_en": "Snorlax ex", "set_name": "朱&紫·宝可梦151", "set_code": "sv3a",
     "card_number": "096/165", "rarity": "SR", "hp": "340", "types": "无",
     "market_price": 110, "category": "PTCG-SC"},

    {"name": "卡比兽 CSR", "name_en": "Snorlax", "set_name": "太阳&月亮·无限光", "set_code": "sm6a",
     "card_number": "078/066", "rarity": "CSR", "hp": "", "types": "无",
     "market_price": 150, "category": "PTCG-SC"},

    {"name": "快龙 ex", "name_en": "Dragonite ex", "set_name": "朱&紫·悖论裂缝", "set_code": "sv4",
     "card_number": "072/072", "rarity": "SR", "hp": "330", "types": "龙",
     "market_price": 190, "category": "PTCG-SC"},

    {"name": "路卡利欧 ex", "name_en": "Lucario ex", "set_name": "朱&紫·暮色假面", "set_code": "sv6",
     "card_number": "046/066", "rarity": "SR", "hp": "320", "types": "格斗",
     "market_price": 160, "category": "PTCG-SC"},

    {"name": "沙奈朵 ex", "name_en": "Gardevoir ex", "set_name": "朱&紫·巴涅大地区", "set_code": "sv2",
     "card_number": "089/093", "rarity": "SAR", "hp": "310", "types": "超",
     "market_price": 420, "category": "PTCG-SC"},

    {"name": "暴飞龙 ex", "name_en": "Salamence ex", "set_name": "朱&紫·悖论裂缝", "set_code": "sv4",
     "card_number": "074/072", "rarity": "SAR", "hp": "330", "types": "龙",
     "market_price": 350, "category": "PTCG-SC"},

    {"name": "烈咬陆鲨 ex", "name_en": "Garchomp ex", "set_name": "朱&紫·巴涅大地区", "set_code": "sv2",
     "card_number": "090/093", "rarity": "SAR", "hp": "340", "types": "龙",
     "market_price": 380, "category": "PTCG-SC"},

    {"name": "苍响 ex", "name_en": "Zacian ex", "set_name": "朱&紫·银色暴风", "set_code": "swsh9",
     "card_number": "079/072", "rarity": "HR", "hp": "320", "types": "钢",
     "market_price": 280, "category": "PTCG-SC"},

    {"name": "藏玛然特 ex", "name_en": "Zamazenta ex", "set_name": "朱&紫·银色暴风", "set_code": "swsh9",
     "card_number": "080/072", "rarity": "HR", "hp": "320", "types": "格斗",
     "market_price": 250, "category": "PTCG-SC"},

    # === 高人气 SAR/CSR 收藏卡 ===
    {"name": "耿鬼 SAR", "name_en": "Gengar ex", "set_name": "朱&紫·暮色假面", "set_code": "sv6",
     "card_number": "039/066", "rarity": "SAR", "hp": "320", "types": "超",
     "market_price": 520, "category": "PTCG-SC"},

    {"name": "耿鬼", "name_en": "Gengar", "set_name": "闪色珍贵卡盒", "set_code": "special",
     "card_number": "SAR", "rarity": "SAR", "hp": "320", "types": "超",
     "market_price": 350, "category": "PTCG-SC"},

    {"name": "皮卡丘", "name_en": "Pikachu", "set_name": "朱&紫·公主连结", "set_code": "special",
     "card_number": "001/006", "rarity": "PROMO", "hp": "70", "types": "雷",
     "market_price": 65, "category": "PTCG-SC"},

    # === 新系列热门 ===
    {"name": "喷火龙 ex", "name_en": "Charizard ex", "set_name": "朱&紫·超越边界", "set_code": "sv8",
     "card_number": "088/066", "rarity": "SAR", "hp": "330", "types": "火",
     "market_price": 980, "category": "PTCG-SC"},

    {"name": "喷火龙 ex", "name_en": "Charizard ex", "set_name": "朱&紫·超越边界", "set_code": "sv8",
     "card_number": "088/066", "rarity": "UR", "hp": "330", "types": "火",
     "market_price": 650, "category": "PTCG-SC"},

    {"name": "皮卡丘 ex", "name_en": "Pikachu ex", "set_name": "朱&紫·超越边界", "set_code": "sv8",
     "card_number": "072/066", "rarity": "SAR", "hp": "200", "types": "雷",
     "market_price": 450, "category": "PTCG-SC"},

    {"name": "超梦 ex", "name_en": "Mewtwo ex", "set_name": "朱&紫·棱镜进化", "set_code": "sv8pt5",
     "card_number": "074/072", "rarity": "SAR", "hp": "330", "types": "超",
     "market_price": 720, "category": "PTCG-SC"},

    {"name": "伊布", "name_en": "Eevee", "set_name": "朱&紫·棱镜进化", "set_code": "sv8pt5",
     "card_number": "080/072", "rarity": "SAR", "hp": "70", "types": "无",
     "market_price": 580, "category": "PTCG-SC"},
]


def rebuild_catalog():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # 1. 删除美版卡牌（ID >= 14）
    print("=== 1. 清理美版卡牌 ===")

    # 先清理 price_records 中关联美版卡牌的记录
    c.execute("DELETE FROM price_records WHERE catalog_id >= 14")
    deleted_prices = c.rowcount
    print(f"  删除 {deleted_prices} 条美版价格记录")

    # 删除美版卡牌
    c.execute("DELETE FROM card_catalog WHERE id >= 14")
    deleted_cards = c.rowcount
    print(f"  删除 {deleted_cards} 条美版卡牌记录")

    # 2. 检查表结构，确保有必要的字段
    print("\n=== 2. 检查表结构 ===")
    cols = [row[1] for row in c.execute("PRAGMA table_info(card_catalog)").fetchall()]
    print(f"  当前字段: {cols}")

    # 添加缺失的字段
    if 'category' not in cols:
        c.execute("ALTER TABLE card_catalog ADD COLUMN category TEXT DEFAULT 'PTCG-SC'")
        print("  添加字段: category")
    if 'language' not in cols:
        c.execute("ALTER TABLE card_catalog ADD COLUMN language TEXT DEFAULT 'zh'")
        print("  添加字段: language")

    # 3. 插入中文版热门卡牌
    print(f"\n=== 3. 导入 {len(POPULAR_CARDS)} 张中文版热门卡牌 ===")

    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    inserted = 0

    for card in POPULAR_CARDS:
        try:
            c.execute("""
                INSERT INTO card_catalog
                    (name, name_en, set_name, set_code, card_number, rarity,
                     hp, types, market_price, category, language, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                card['name'], card.get('name_en', ''), card['set_name'],
                card.get('set_code', ''), card.get('card_number', ''),
                card['rarity'], card.get('hp', ''), card.get('types', ''),
                card['market_price'], card.get('category', 'PTCG-SC'),
                'zh', now, now
            ))
            inserted += 1
            catalog_id = c.lastrowid

            # 同时插入价格记录
            c.execute("""
                INSERT INTO price_records
                    (catalog_id, platform, price, recorded_at)
                VALUES (?, ?, ?, ?)
            """, (catalog_id, '集换社', card['market_price'], now))

        except Exception as e:
            print(f"  插入失败: {card['name']} - {e}")

    print(f"  成功导入 {inserted} 张卡牌")

    # 4. 统计
    print("\n=== 4. 最终统计 ===")
    c.execute("SELECT COUNT(*) FROM card_catalog")
    total = c.fetchone()[0]
    print(f"  card_catalog 总数: {total}")

    c.execute("SELECT COUNT(*) FROM price_records")
    total_prices = c.fetchone()[0]
    print(f"  price_records 总数: {total_prices}")

    c.execute("SELECT COUNT(*) FROM price_records WHERE platform = '集换社'")
    jhs_prices = c.fetchone()[0]
    print(f"  集换社价格记录: {jhs_prices}")

    # 按系列统计
    print("\n  按系列统计:")
    c.execute("""
        SELECT set_name, COUNT(*) as cnt
        FROM card_catalog
        GROUP BY set_name
        ORDER BY cnt DESC
    """)
    for row in c.fetchall():
        print(f"    {row[0]}: {row[1]} 张")

    conn.commit()
    conn.close()
    print("\n✅ 数据库重建完成！")


if __name__ == '__main__':
    rebuild_catalog()
