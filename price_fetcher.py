"""
价格抓取模块 - 从多个数据源抓取宝可梦卡牌价格

数据源：
1. Pokemon TCG API (api.pokemontcg.io) - 国外参考价
2. 集换社 (jihuanshe.com) - 国内交易价（待实现）
3. 咸鱼 - 二手交易价（待实现）

使用方法：
    from price_fetcher import fetch_all_catalog_prices, fetch_catalog_price
    fetch_all_catalog_prices()  # 抓取所有目录卡牌价格
"""

import time
import json
import logging
from datetime import datetime
import requests

from db import (
    get_all_catalog, add_catalog_price_record,
    get_catalog_latest_price, get_db
)
from config import TCG_API_KEY, TCG_API_BASE, SCRAPER_TIMEOUT, SCRAPER_USER_AGENT

logger = logging.getLogger(__name__)

# 汇率（ approximate）
USD_TO_CNY = 7.2
EUR_TO_CNY = 7.8


def _get_tcg_headers():
    """Build request headers for TCG API"""
    headers = {
        'User-Agent': SCRAPER_USER_AGENT,
        'Accept': 'application/json',
    }
    if TCG_API_KEY:
        headers['X-Api-Key'] = TCG_API_KEY
    return headers


def search_tcg_catalog_card(catalog_item):
    """
    Search TCG API for a catalog item.
    
    Args:
        catalog_item: dict with name, name_en, set_name, card_number
    
    Returns:
        List of matched cards with full info (prices, hp, types, attacks, etc.)
    """
    # Build search query - try English name first, then Chinese
    queries = []
    
    if catalog_item.get('name_en'):
        # Try exact match first
        queries.append(f'name:"{catalog_item["name_en"]}"')
        # Also try without ex/VMAX/etc suffix for broader match
        name_en_simple = catalog_item['name_en'].split(' ex ')[0].split(' VMAX')[0].split(' V ')[0].strip()
        if name_en_simple != catalog_item['name_en']:
            queries.append(f'name:"{name_en_simple}"')
    
    if catalog_item.get('name') and not queries:
        # Use Chinese name as fallback
        queries.append(catalog_item['name'])
    
    # Try each query until we get results
    for query in queries:
        url = f"{TCG_API_BASE}/cards"
        params = {'q': query, 'pageSize': 10}
        
        try:
            res = requests.get(
                url, params=params,
                headers=_get_tcg_headers(),
                timeout=SCRAPER_TIMEOUT
            )
            res.raise_for_status()
            data = res.json().get('data', [])
            
            if data:
                # Filter by set if set_code is available
                if catalog_item.get('set_code'):
                    filtered = [c for c in data if c.get('set', {}).get('id') == catalog_item['set_code']]
                    if filtered:
                        data = filtered
                
                results = []
                for card in data:
                    # Extract market prices
                    tcg_prices = card.get('tcgplayer', {}).get('prices') or {}
                    market_prices = card.get('cardmarket', {}).get('prices') or {}
                    
                    best_usd = None
                    for category in ['normal', 'holofoil', 'reverseHolofoil']:
                        cat_prices = tcg_prices.get(category, {})
                        if cat_prices.get('market'):
                            p = float(cat_prices['market'])
                            best_usd = p if best_usd is None or p > best_usd else best_usd
                    
                    best_eur = None
                    if market_prices.get('avg1'):
                        best_eur = float(market_prices['avg1'])
                    
                    # Build full card info
                    card_info = {
                        'tcg_id': card.get('id'),
                        'name': card.get('name'),
                        'set_name': card.get('set', {}).get('name'),
                        'set_id': card.get('set', {}).get('id'),
                        'number': card.get('number'),
                        'rarity': card.get('rarity'),
                        'hp': card.get('hp'),
                        'types': card.get('types', []),
                        'subtypes': card.get('subtypes', []),
                        'evolves_from': card.get('evolvesFrom'),
                        'abilities': card.get('abilities', []),
                        'attacks': card.get('attacks', []),
                        'weaknesses': card.get('weaknesses', []),
                        'retreat_cost': len(card.get('retreatCost', [])),
                        'artist': card.get('artist'),
                        'flavor_text': card.get('flavorText'),
                        'national_pokedex_numbers': card.get('nationalPokedexNumbers', []),
                        'legalities': card.get('legalities', {}),
                        'image_url': card.get('images', {}).get('large'),
                        'usd_price': best_usd,
                        'eur_price': best_eur,
                        'cny_price': round(best_usd * USD_TO_CNY, 2) if best_usd else None,
                    }
                    results.append(card_info)
                
                logger.info(f"TCG search for '{catalog_item['name']}': {len(results)} results")
                return results
        
        except requests.exceptions.RequestException as e:
            logger.error(f"TCG API request failed: {e}")
            continue
        except Exception as e:
            logger.error(f"TCG API error: {e}")
            continue
    
    logger.warning(f"TCG search for '{catalog_item['name']}': no results")
    return []


def fetch_catalog_price(catalog_id, source='tcg'):
    """
    Fetch price for a catalog item and store in price_records.
    
    Args:
        catalog_id: ID in card_catalog table
        source: 'tcg' (Pokemon TCG API) or 'jihuanshe' (TODO)
    
    Returns:
        Dict with status and price info
    """
    from db import get_db
    
    conn = get_db()
    catalog_item = conn.execute(
        'SELECT * FROM card_catalog WHERE id = ?', (catalog_id,)
    ).fetchone()
    conn.close()
    
    if not catalog_item:
        return {'success': False, 'message': f'Catalog item {catalog_id} not found'}
    
    catalog_item = dict(catalog_item)
    
    if source == 'tcg':
        return _fetch_from_tcg(catalog_item)
    elif source == 'jihuanshe':
        return _fetch_from_jihuanshe(catalog_item)
    else:
        return {'success': False, 'message': f'Unknown source: {source}'}


def _fetch_from_tcg(catalog_item):
    """Fetch price and full card info from Pokemon TCG API"""
    results = search_tcg_catalog_card(catalog_item)
    
    if not results:
        return {
            'success': False,
            'message': f'No results from TCG API for "{catalog_item["name"]}"',
            'catalog_id': catalog_item['id']
        }
    
    # Use the first (best) match
    best = results[0]
    catalog_id = catalog_item['id']
    
    # ===== 1. Update card_catalog with full info =====
    conn = get_db()
    try:
        # Build update fields
        update_fields = []
        params = []
        
        if best.get('tcg_id'):
            update_fields.append('tcg_id = ?')
            params.append(best['tcg_id'])
        
        if best.get('hp') is not None:
            update_fields.append('hp = ?')
            params.append(best['hp'])
        
        if best.get('types'):
            update_fields.append('types = ?')
            params.append(json.dumps(best['types'], ensure_ascii=False))
        
        if best.get('subtypes'):
            update_fields.append('subtypes = ?')
            params.append(json.dumps(best['subtypes'], ensure_ascii=False))
        
        if best.get('evolves_from'):
            update_fields.append('evolves_from = ?')
            params.append(best['evolves_from'])
        
        if best.get('abilities'):
            update_fields.append('abilities = ?')
            params.append(json.dumps(best['abilities'], ensure_ascii=False))
        
        if best.get('attacks'):
            update_fields.append('attacks = ?')
            params.append(json.dumps(best['attacks'], ensure_ascii=False))
        
        if best.get('weaknesses'):
            update_fields.append('weaknesses = ?')
            params.append(json.dumps(best['weaknesses'], ensure_ascii=False))
        
        if best.get('retreat_cost') is not None:
            update_fields.append('retreat_cost = ?')
            params.append(best['retreat_cost'])
        
        if best.get('artist'):
            update_fields.append('artist = ?')
            params.append(best['artist'])
        
        if best.get('flavor_text'):
            update_fields.append('flavor_text = ?')
            params.append(best['flavor_text'])
        
        if best.get('national_pokedex_numbers'):
            update_fields.append('national_pokedex_numbers = ?')
            params.append(json.dumps(best['national_pokedex_numbers'], ensure_ascii=False))
        
        if best.get('legalities'):
            update_fields.append('legalities = ?')
            params.append(json.dumps(best['legalities'], ensure_ascii=False))
        
        if best.get('image_url'):
            update_fields.append('image_url = ?')
            params.append(best['image_url'])
        
        if best.get('set_id'):
            update_fields.append('set_code = ?')
            params.append(best['set_id'])
        
        if update_fields:
            params.append(catalog_id)
            sql = f"UPDATE card_catalog SET {', '.join(update_fields)}, updated_at = CURRENT_TIMESTAMP WHERE id = ?"
            conn.execute(sql, params)
            conn.commit()
            logger.info(f"Updated catalog #{catalog_id} with full TCG info")
    
    except Exception as e:
        logger.error(f"Failed to update catalog #{catalog_id}: {e}")
    finally:
        conn.close()
    
    # ===== 2. Add price records =====
    prices_added = []
    
    # Add USD price (converted to CNY)
    if best['usd_price']:
        price_cny = best['cny_price']
        add_catalog_price_record(catalog_id, 'TCG-USD', price_cny)
        prices_added.append({
            'platform': 'TCG-USD',
            'price': price_cny,
            'original': f'${best["usd_price"]:.2f}'
        })
    
    # Add EUR price (converted to CNY)
    if best['eur_price']:
        price_cny = round(best['eur_price'] * EUR_TO_CNY, 2)
        add_catalog_price_record(catalog_id, 'TCG-EUR', price_cny)
        prices_added.append({
            'platform': 'TCG-EUR',
            'price': price_cny,
            'original': f'€{best["eur_price"]:.2f}'
        })
    
    logger.info(f"Price fetched for catalog #{catalog_id} ({catalog_item['name']}): {len(prices_added)} records")
    
    return {
        'success': True,
        'catalog_id': catalog_id,
        'catalog_name': catalog_item['name'],
        'matched_name': best['name'],
        'prices': prices_added,
        'card_info': {
            'hp': best.get('hp'),
            'types': best.get('types'),
            'rarity': best.get('rarity'),
            'artist': best.get('artist'),
        }
    }


def _fetch_from_jihuanshe(catalog_item):
    """
    Fetch price from 集换社 (JiHuanShe).
    TODO: Implement web scraping
    """
    logger.warning("JiHuanShe scraping not yet implemented")
    return {
        'success': False,
        'message': '集换社抓取尚未实现',
        'catalog_id': catalog_item['id']
    }


def fetch_all_catalog_prices(limit=None, source='tcg'):
    """
    Fetch prices for all catalog items.
    
    Args:
        limit: Max number of cards to fetch (None = all)
        source: Price source ('tcg', 'jihuanshe')
    
    Returns:
        Summary dict
    """
    catalog, _ = get_all_catalog()
    
    if limit:
        catalog = catalog[:limit]
    
    total = len(catalog)
    success_count = 0
    fail_count = 0
    results = []
    
    print(f"\n{'='*60}")
    print(f"开始抓取价格: {total} 张卡牌 (数据源: {source})")
    print(f"{'='*60}\n")
    
    for i, item in enumerate(catalog):
        print(f"[{i+1}/{total}] {item['name']} ({item['set_name']}) ... ", end='', flush=True)
        
        result = fetch_catalog_price(item['id'], source=source)
        results.append(result)
        
        if result.get('success'):
            success_count += 1
            prices_str = ', '.join([f"{p['platform']}: ¥{p['price']}" for p in result.get('prices', [])])
            print(f"✓ {prices_str}")
        else:
            fail_count += 1
            print(f"✗ {result.get('message', 'Unknown error')}")
        
        # Rate limiting
        if source == 'tcg' and i < total - 1:
            time.sleep(2.5)  # TCG API limit: ~30 requests/minute
    
    print(f"\n{'='*60}")
    print(f"完成! 成功: {success_count}, 失败: {fail_count}, 总计: {total}")
    print(f"{'='*60}\n")
    
    return {
        'total': total,
        'success': success_count,
        'failed': fail_count,
        'results': results,
    }


def fetch_unpriced_catalog(source='tcg'):
    """
    Fetch prices only for catalog items that don't have recent price records.
    """
    from db import get_all_catalog, get_catalog_latest_price
    
    catalog, _ = get_all_catalog()
    
    # Filter: only items without recent price (older than 7 days)
    to_fetch = []
    for item in catalog:
        latest = get_catalog_latest_price(item['id'])
        if not latest or not latest.get('avg'):
            to_fetch.append(item)
    
    if not to_fetch:
        print("所有卡牌都有价格数据!")
        return {'total': 0, 'success': 0, 'failed': 0}
    
    print(f"\n找到 {len(to_fetch)} 张卡牌需要抓取价格...\n")
    
    total = len(to_fetch)
    success_count = 0
    fail_count = 0
    
    for i, item in enumerate(to_fetch):
        print(f"[{i+1}/{total}] {item['name']} ... ", end='', flush=True)
        
        result = fetch_catalog_price(item['id'], source=source)
        
        if result.get('success'):
            success_count += 1
            prices_str = ', '.join([f"{p['platform']}: ¥{p['price']}" for p in result.get('prices', [])])
            print(f"✓ {prices_str}")
        else:
            fail_count += 1
            print(f"✗ {result.get('message', 'Unknown error')}")
        
        if source == 'tcg' and i < total - 1:
            time.sleep(2.5)
    
    print(f"\n完成! 成功: {success_count}, 失败: {fail_count}, 总计: {total}\n")
    
    return {
        'total': total,
        'success': success_count,
        'failed': fail_count,
    }


def update_user_card_prices(user_id=None):
    """
    Update market_price field for user's cards based on latest catalog prices.
    This allows the dashboard to show accurate valuations.
    """
    from db import get_all_cards, get_catalog_latest_price, update_card
    
    cards = get_all_cards(user_id=user_id)
    updated = 0
    
    for card in cards:
        if not card.get('catalog_id'):
            continue
        
        latest = get_catalog_latest_price(card['catalog_id'])
        if latest and latest.get('avg'):
            # Update card's market_price
            update_card(card['id'], {'market_price': latest['avg']})
            updated += 1
    
    print(f"\n更新了 {updated} 张卡牌的市场价格\n")
    return updated


if __name__ == '__main__':
    """CLI entry point"""
    import sys
    import argparse
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s'
    )
    
    parser = argparse.ArgumentParser(description='价格抓取工具')
    parser.add_argument('--all', action='store_true', help='抓取所有卡牌价格')
    parser.add_argument('--unpriced', action='store_true', help='只抓取没有价格的卡牌')
    parser.add_argument('--catalog-id', type=int, help='抓取指定 catalog_id 的价格')
    parser.add_argument('--source', default='tcg', choices=['tcg', 'jihuanshe'],
                        help='数据源 (默认: tcg)')
    parser.add_argument('--limit', type=int, help='限制抓取数量')
    parser.add_argument('--update-market', action='store_true', help='更新用户卡牌的 market_price')
    
    args = parser.parse_args()
    
    if args.catalog_id:
        # Fetch single card
        result = fetch_catalog_price(args.catalog_id, source=args.source)
        print(result)
    
    elif args.all:
        # Fetch all
        fetch_all_catalog_prices(limit=args.limit, source=args.source)
    
    elif args.unpriced:
        # Fetch only unpriced
        fetch_unpriced_catalog(source=args.source)
    
    elif args.update_market:
        # Update user card market prices
        update_user_card_prices()
    
    else:
        parser.print_help()
