#!/usr/bin/env python3
"""
将简体中文卡牌数据导入到 Supabase（测试版 - 前10张）
"""

import json
import requests
import time

# Supabase 配置
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://your-project.supabase.co")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")

headers = {
    "apikey": SUPABASE_SERVICE_KEY,
    "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation"
}

# 读取 JSON 文件
print("正在读取简体中文卡牌数据...")
with open('/Volumes/资料/workbuddy/kapai/ptcg_cards_chs.json', 'r', encoding='utf-8') as f:
    sets_data = json.load(f)

# 属性映射
attribute_map = {
    "1": "Grass",
    "2": "Fire",
    "3": "Water",
    "4": "Lightning",
    "5": "Psychic",
    "6": "Ice",
    "7": "Dragon",
    "8": "Darkness",
    "9": "Metal",
    "10": "Fairy",
    "11": "Colorless"
}

# 稀有度映射
rarity_map = {
    "1": "Common",
    "2": "Uncommon",
    "3": "Rare",
    "4": "Rare Holo",
    "5": "Rare Ultra",
    "6": "Rare Secret",
    "7": "Rare Ultra"
}

# 准备测试数据（前10张卡牌）
test_cards = []
count = 0

for card_set in sets_data:
    set_id = card_set.get('id')
    set_name = card_set.get('name', '')
    set_code = card_set.get('commodityCode', '')
    set_series = card_set.get('seriesText', '')
    
    cards = card_set.get('cards', [])
    for card in cards:
        if count >= 10:
            break
            
        details = card.get('details', {})
        
        # 构建卡牌数据（使用正确的字段名）
        card_data = {
            "tcg_id": f"PTCG-{set_id}-{card.get('id')}",
            "name": details.get('cardName', ''),
            "name_en": None,  # 暂时留空
            "set_name": set_name,
            "set_code": set_code,
            "card_number": details.get('collectionNumber', ''),
            "rarity": rarity_map.get(str(details.get('rarity', '')), details.get('rarityText', '')),
            "image_url": None,  # 暂时留空
            "language": "zh",
            "hp": details.get('hp'),
            "types": [attribute_map.get(str(details.get('attribute', '')), '')] if details.get('attribute') else None,
            "subtypes": [details.get('cardTypeText', '')] if details.get('cardTypeText') else None,
            "evolves_from": details.get('evolveText', ''),
            "artist": details.get('illustratorName', ''),
            "category": "PTCG-CHS"
        }
        
        test_cards.append(card_data)
        count += 1
    
    if count >= 10:
        break

print(f"\n准备导入 {len(test_cards)} 张测试卡牌:")
for i, card in enumerate(test_cards):
    print(f"  {i+1}. {card['name']} ({card['set_name']})")

# 测试导入
print(f"\n开始导入...")
try:
    response = requests.post(
        f"{SUPABASE_URL}/rest/v1/card_catalog",
        headers=headers,
        json=test_cards
    )
    
    print(f"状态码: {response.status_code}")
    
    if response.status_code == 201:
        print(f"\n✅ 测试导入成功！")
        data = response.json()
        print(f"已导入 {len(data)} 条数据")
    else:
        print(f"\n❌ 测试导入失败")
        print(f"响应: {response.text[:1000]}")
        
except Exception as e:
    print(f"\n❌ 异常: {e}")
