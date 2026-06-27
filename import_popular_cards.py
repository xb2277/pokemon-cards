"""
批量导入热门宝可梦卡牌到 card_catalog

从 TCG API 搜索热门宝可梦卡牌，批量插入数据库。
运行方式：
    python3 import_popular_cards.py
"""

import sys
import json
import time
import logging
from datetime import datetime

# 添加项目路径
sys.path.insert(0, '.')

from db import get_db
from config import TCG_API_BASE, TCG_API_KEY, SCRAPER_TIMEOUT, SCRAPER_USER_AGENT

import requests

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)

# 热门宝可梦搜索关键词
POPULAR_POKEMON = [
    'Pikachu', 'Charizard', 'Mewtwo', 'Rayquaza', 'Lugia',
    'Gengar', 'Eevee', 'Snorlax', 'Dragonite', 'Mew',
    'Zapdos', 'Articuno', 'Moltres', 'Gyarados', 'Tyranitar',
    'Umbreon', 'Espeon', 'Sylveon', 'Leafeon', 'Glaceon',
    'Vaporeon', 'Jolteon', 'Flareon', 'Blastoise', 'Venusaur',
    'Lucario', 'Garchomp', 'Metagross', 'Salamence', 'Typhlosion',
]

def search_pokemon_cards(pokemon_name, page_size=20):
    """
    从 TCG API 搜索指定宝可梦的卡牌
    """
    url = f"{TCG_API_BASE}/cards"
    params = {
        'q': f'name:"{pokemon_name}" supertype:"Pokemon"',
        'pageSize': page_size,
        'orderBy': '-set.releaseDate',  # 最新的在前
    }
    
    headers = {'User-Agent': SCRAPER_USER_AGENT, 'Accept': 'application/json'}
    if TCG_API_KEY:
        headers['X-Api-Key'] = TCG_API_KEY
    
    try:
        res = requests.get(url, params=params, headers=headers, timeout=SCRAPER_TIMEOUT)
        res.raise_for_status()
        data = res.json().get('data', [])
        logger.info(f"搜索 '{pokemon_name}': 找到 {len(data)} 张卡牌")
        return data
    except Exception as e:
        logger.error(f"搜索 '{pokemon_name}' 失败: {e}")
        return []

def insert_catalog_card(card_data):
    """
    将 TCG API 的卡牌数据插入 card_catalog 表
    如果卡牌已存在（按 tcg_id 或 name+set_code 判断），则跳过
    """
    conn = get_db()
    
    try:
        # 检查是否已存在
        existing = conn.execute(
            'SELECT id FROM card_catalog WHERE tcg_id = ? OR (name = ? AND set_code = ?)',
            (card_data.get('id'), card_data.get('name'), card_data.get('set', {}).get('id'))
        ).fetchone()
        
        if existing:
            logger.debug(f"卡牌已存在: {card_data.get('name')} ({card_data.get('set', {}).get('name')})")
            conn.close()
            return False, existing['id']
        
        # 提取数据
        card_id = card_data.get('id')
        name = card_data.get('name')
        set_info = card_data.get('set', {})
        set_code = set_info.get('id')
        set_name = set_info.get('name')
        card_number = card_data.get('number')
        rarity = card_data.get('rarity', '')
        hp = card_data.get('hp')
        types = json.dumps(card_data.get('types', []), ensure_ascii=False)
        subtypes = json.dumps(card_data.get('subtypes', []), ensure_ascii=False)
        evolves_from = card_data.get('evolvesFrom')
        abilities = json.dumps(card_data.get('abilities', []), ensure_ascii=False)
        attacks = json.dumps(card_data.get('attacks', []), ensure_ascii=False)
        weaknesses = json.dumps(card_data.get('weaknesses', []), ensure_ascii=False)
        retreat_cost = len(card_data.get('retreatCost', []))
        artist = card_data.get('artist')
        flavor_text = card_data.get('flavorText')
        national_pokedex_numbers = json.dumps(card_data.get('nationalPokedexNumbers', []), ensure_ascii=False)
        legalities = json.dumps(card_data.get('legalities', {}), ensure_ascii=False)
        image_url = card_data.get('images', {}).get('large')
        
        # 插入
        conn.execute('''
            INSERT INTO card_catalog (
                tcg_id, name, set_code, set_name, card_number, rarity,
                hp, types, subtypes, evolves_from, abilities, attacks,
                weaknesses, retreat_cost, artist, flavor_text,
                national_pokedex_numbers, legalities, image_url,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        ''', (
            card_id, name, set_code, set_name, card_number, rarity,
            hp, types, subtypes, evolves_from, abilities, attacks,
            weaknesses, retreat_cost, artist, flavor_text,
            national_pokedex_numbers, legalities, image_url,
        ))
        
        conn.commit()
        new_id = conn.execute('SELECT last_insert_rowid()').fetchone()[0]
        logger.info(f"✓ 插入新卡牌: {name} ({set_name}) [ID: {new_id}]")
        conn.close()
        return True, new_id
        
    except Exception as e:
        logger.error(f"插入卡牌失败: {e}")
        conn.close()
        return False, None

def main():
    logger.info("="*60)
    logger.info("开始批量导入热门宝可梦卡牌")
    logger.info("="*60)
    
    total_imported = 0
    total_skipped = 0
    failed_searches = 0
    
    for i, pokemon in enumerate(POPULAR_POKEMON):
        logger.info(f"\n[{i+1}/{len(POPULAR_POKEMON)}] 搜索: {pokemon}")
        
        cards = search_pokemon_cards(pokemon, page_size=10)  # 每个宝可梦取前 10 张
        
        if not cards:
            failed_searches += 1
            continue
        
        for card in cards:
            success, card_id = insert_catalog_card(card)
            if success:
                total_imported += 1
            else:
                total_skipped += 1
        
        # 限速，避免 TCG API 限流
        if i < len(POPULAR_POKEMON) - 1:
            time.sleep(1.5)
    
    logger.info("\n" + "="*60)
    logger.info(f"导入完成! 新增: {total_imported}, 跳过(已存在): {total_skipped}, 搜索失败: {failed_searches}")
    logger.info("="*60)

if __name__ == '__main__':
    main()
