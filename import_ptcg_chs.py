#!/usr/bin/env python3
"""
将 CrystMiku/PokemonTCG-Data-Raw 的简体中文卡牌数据导入到 Supabase
数据来源：https://github.com/CrystMiku/PokemonTCG-Data-Raw
"""

import json
import requests
import time
from datetime import datetime

# Supabase 配置
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://your-project.supabase.co")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")

#  headers
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

# 属性映射（从数据来看，attribute 是数字）
attribute_map = {
    "1": "草",
    "2": "火",
    "3": "水",
    "4": "雷",
    "5": "超",
    "6": "冰",
    "7": "龙",
    "8": "恶",
    "9": "钢",
    "10": " fairy",  # 妖精
    "11": "无色"
}

# 稀有度映射
rarity_map = {
    "1": "C",
    "2": "U",
    "3": "R",
    "4": "RR",
    "5": "SR",
    "6": "SSR",
    "7": "UR"
}

def get_image_url(set_id, image_path):
    """构建卡牌图片 URL"""
    # 根据 imagePath 构建 URL
    # imagePath 格式如 "1/1.png"，表示卡包ID/卡牌ID.png
    base_url = "https://pokemon-release.oss-cn-shanghai.aliyuncs.com/image"
    return f"{base_url}/{set_id}/{image_path}"

def import_cards():
    """导入卡牌数据到 card_catalog 表"""
    cards_to_insert = []
    
    for card_set in sets_data:
        set_id = card_set.get('id')
        set_name = card_set.get('name', '')
        set_series = card_set.get('seriesText', '')
        
        print(f"\n处理卡包: {set_name} ({set_series})")
        
        cards = card_set.get('cards', [])
        for card in cards:
            details = card.get('details', {})
            
            # 构建卡牌数据
            card_data = {
                "tcg_id": f"PTCG-{set_id}-{card.get('id')}",  # 生成唯一 ID
                "name": details.get('cardName', ''),
                "set_name": set_name,
                "set_series": set_series,
                "rarity": rarity_map.get(str(details.get('rarity', '')), details.get('rarityText', '')),
                "image_url": get_image_url(set_id, card.get('imagePath', '')),
                "language": "zh",  # 简体中文
                "hp": details.get('hp'),
                "attribute": attribute_map.get(str(details.get('attribute', '')), ''),
                "card_number": details.get('collectionNumber', ''),
                "illustrator": details.get('illustratorName', '')
            }
            
            cards_to_insert.append(card_data)
    
    print(f"\n共 {len(cards_to_insert)} 张卡牌待导入")
    
    # 分批导入（每批 100 条）
    batch_size = 100
    success_count = 0
    error_count = 0
    
    for i in range(0, len(cards_to_insert), batch_size):
        batch = cards_to_insert[i:i+batch_size]
        
        try:
            # 使用 Supabase REST API 插入数据
            response = requests.post(
                f"{SUPABASE_URL}/rest/v1/card_catalog",
                headers=headers,
                json=batch
            )
            
            if response.status_code == 201:
                success_count += len(batch)
                print(f"  批次 {i//batch_size + 1}: 成功导入 {len(batch)} 条")
            else:
                error_count += len(batch)
                print(f"  批次 {i//batch_size + 1}: 失败 - {response.status_code} {response.text}")
                
        except Exception as e:
            error_count += len(batch)
            print(f"  批次 {i//batch_size + 1}: 异常 - {e}")
        
        # 避免请求过快
        time.sleep(0.5)
    
    print(f"\n导入完成！")
    print(f"  成功: {success_count} 条")
    print(f"  失败: {error_count} 条")

if __name__ == "__main__":
    import_cards()
