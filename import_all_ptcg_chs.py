#!/usr/bin/env python3
"""
将简体中文卡牌数据导入到 Supabase（完整版）
数据来源：CrystMiku/PokemonTCG-Data-Raw
"""

import json
import requests
import time
from datetime import datetime

# Supabase 配置
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://your-project.supabase.co")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")

headers = {
    "apikey": SUPABASE_SERVICE_KEY,
    "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=minimal"
}

# 读取 JSON 文件
print("正在读取简体中文卡牌数据...")
with open('/Volumes/资料/workbuddy/kapai/ptcg_cards_chs.json', 'r', encoding='utf-8') as f:
    sets_data = json.load(f)

print(f"共 {len(sets_data)} 个卡包")

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

def import_all_cards():
    """导入所有卡牌数据到 card_catalog 表"""
    cards_to_insert = []
    
    for card_set in sets_data:
        set_id = card_set.get('id')
        set_name = card_set.get('name', '')
        set_code = card_set.get('commodityCode', '')
        set_series = card_set.get('seriesText', '')
        
        cards = card_set.get('cards', [])
        for card in cards:
            details = card.get('details', {})
            
            # 构建卡牌数据
            card_data = {
                "tcg_id": f"PTCG-{set_id}-{card.get('id')}",
                "name": details.get('cardName', ''),
                "name_en": None,
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
            
            cards_to_insert.append(card_data)
    
    print(f"\n共 {len(cards_to_insert)} 张卡牌待导入")
    
    # 分批导入（每批 100 条）
    batch_size = 100
    success_count = 0
    error_count = 0
    error_messages = []
    
    for i in range(0, len(cards_to_insert), batch_size):
        batch = cards_to_insert[i:i+batch_size]
        
        try:
            response = requests.post(
                f"{SUPABASE_URL}/rest/v1/card_catalog",
                headers=headers,
                json=batch
            )
            
            if response.status_code == 201:
                success_count += len(batch)
                print(f"  批次 {i//batch_size + 1}: 成功导入 {len(batch)} 条 (总计: {success_count})")
            else:
                error_count += len(batch)
                error_msg = f"批次 {i//batch_size + 1}: {response.status_code} {response.text[:200]}"
                error_messages.append(error_msg)
                print(f"  批次 {i//batch_size + 1}: 失败 - {response.status_code}")
                
        except Exception as e:
            error_count += len(batch)
            error_msg = f"批次 {i//batch_size + 1}: {str(e)}"
            error_messages.append(error_msg)
            print(f"  批次 {i//batch_size + 1}: 异常 - {e}")
        
        # 避免请求过快
        time.sleep(0.3)
    
    print(f"\n导入完成！")
    print(f"  成功: {success_count} 条")
    print(f"  失败: {error_count} 条")
    
    if error_messages:
        print(f"\n错误详情:")
        for msg in error_messages[:10]:  # 只显示前10个错误
            print(f"  {msg}")

if __name__ == "__main__":
    start_time = datetime.now()
    import_all_cards()
    end_time = datetime.now()
    print(f"\n总耗时: {(end_time - start_time).total_seconds():.2f} 秒")
