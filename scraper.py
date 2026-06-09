# Pokemon Cards Manager - Price Scraper Module

"""
价格爬虫模块，用于从多个数据源抓取卡牌价格信息。

支持的数据源：
1. Pokemon TCG API (api.pokemontcg.io) - 官方免费 API
2. TCGPlayer (tcgplayer.com) - 通过 Pokemon TCG API 间接获取

使用方法：
    from scraper import search_tcg_cards, get_tcg_card_price, fetch_price_for_card

注意：
- Pokemon TCG API 免费版每分钟 30 次请求限制
- 建议在 config.py 中配置 TCG_API_KEY 以获得更高限额（免费注册）
"""

import json
import time
import logging
from datetime import datetime
import requests as req_lib

import config
from db import add_price_record, get_card, update_card

logger = logging.getLogger(__name__)

# USD to CNY exchange rate (approximate)
USD_TO_CNY = 7.2


def _get_headers():
    """Build request headers with optional API key"""
    headers = {
        'User-Agent': config.SCRAPER_USER_AGENT,
        'Accept': 'application/json',
    }
    if config.TCG_API_KEY:
        headers['X-Api-Key'] = config.TCG_API_KEY
    return headers


# ============ Pokemon TCG API ============

def search_tcg_cards(query: str, limit: int = 10):
    """
    Search for cards on the Pokemon TCG API.

    Args:
        query: Card name or keyword (e.g., "Pikachu VMAX")
        limit: Max number of results

    Returns:
        List of card dicts with name, id, set info, images, and prices.
    """
    url = f"{config.TCG_API_BASE}/cards"
    params = {'q': query, 'pageSize': limit}

    try:
        res = req_lib.get(
            url, params=params, headers=_get_headers(),
            timeout=config.SCRAPER_TIMEOUT
        )
        res.raise_for_status()
        data = res.json().get('data', [])

        results = []
        for card in data[:limit]:
            images = card.get('images', {})
            tcg_prices = card.get('tcgplayer', {}).get('prices') or {}
            market_prices = card.get('cardmarket', {}).get('prices') or {}

            # Extract best available market price from TCGPlayer
            best_usd = None
            for category in ['normal', 'holofoil', 'reverseHolofoil']:
                cat_prices = tcg_prices.get(category, {})
                if cat_prices.get('market'):
                    p = float(cat_prices['market'])
                    best_usd = p if best_usd is None or p > best_usd else best_usd

            # Extract from Cardmarket (EUR)
            best_eur = None
            if market_prices.get('avg1'):
                best_eur = float(market_prices['avg1'])

            results.append({
                'id': card.get('id'),
                'name': card.get('name'),
                'set_name': card.get('set', {}).get('name'),
                'number': card.get('number'),
                'rarity': card.get('rarity'),
                'image_small': images.get('small', ''),
                'image_large': images.get('large', ''),
                'usd_market_price': best_usd,
                'eur_avg_price': best_eur,
                'cny_estimated_price': round(best_usd * USD_TO_CNY, 2) if best_usd else None,
            })

        logger.info(f"TCG search '{query}': found {len(results)} results")
        return results

    except req_lib.exceptions.HTTPError as e:
        logger.error(f"TCG API HTTP error: {e.response.status_code}")
        return []
    except Exception as e:
        logger.error(f"TCG API error: {e}")
        return []


def get_tcg_card_by_id(tcg_id: str):
    """
    Get a single card's details by its TCG ID.

    Args:
        tcg_id: The Pokemon TCG API card UUID.

    Returns:
        Card dict or None.
    """
    try:
        res = req_lib.get(
            f"{config.TCG_API_BASE}/cards/{tcg_id}",
            headers=_get_headers(),
            timeout=config.SCRAPER_TIMEOUT
        )
        res.raise_for_status()
        card = res.json().get('data', {})
        return card
    except Exception as e:
        logger.error(f"Failed to fetch TCG card {tcg_id}: {e}")
        return None


# ============ Price Fetching for Local Cards ============

def fetch_price_for_card(card_id: int):
    """
    Fetch current price for a local card record and store it in the database.
    Uses the card's English name (if set) or Chinese name to search TCG API.

    Args:
        card_id: The local database card ID.

    Returns:
        Dict with status and price info.
    """
    card = get_card(card_id)
    if not card:
        return {'success': False, 'message': 'Card not found'}

    # Determine search query
    query = card.get('name_en') or card.get('name')

    if len(query.strip()) < 2:
        return {'success': False, 'message': 'Card name too short'}

    logger.info(f"Fetching price for card #{card_id}: {query}")

    try:
        results = search_tcg_cards(query, limit=3)

        if not results:
            return {
                'success': False,
                'message': f'No results on TCG API for "{query}"',
                'hint': 'Try setting the English name for better matching'
            }

        best_match = results[0]
        price_info = {
            'card_id': card_id,
            'search_query': query,
            'matched_name': best_match['name'],
            'matched_set': best_match['set_name'],
        }

        # Record prices from all available sources
        prices_added = []

        if best_match['usd_market_price']:
            cny_price = best_match['cny_estimated_price']
            add_price_record(card_id, 'pokemontcg-usd', cny_price, 'CNY')
            prices_added.append({
                'platform': 'pokemontcg-usd',
                'price': cny_price,
                'currency': 'CNY',
                'source': f'TCGPlayer ${best_match["usd_market_price"]:.2f}'
            })
            price_info['price_cny'] = cny_price

        if best_match['eur_avg_price']:
            cny_from_eur = round(best_match['eur_avg_price'] * 7.8, 2)  # EUR to CNY
            add_price_record(card_id, 'pokemontcg-eur', cny_from_eur, 'CNY')
            prices_added.append({
                'platform': 'pokemontcg-eur',
                'price': cny_from_eur,
                'currency': 'CNY',
                'source': f'CardMarket \u20ac{best_match["eur_avg_price"]:.2f}'
            })

        # Update card with TCG ID for future reference
        if best_match['id']:
            update_card(card_id, {'tcg_id': best_match['id']})

        logger.info(f"Price fetched for {query}: {len(prices_added)} price records added")

        return {
            'success': True,
            'card_name': query,
            'matched': best_match['name'],
            'prices': prices_added,
            **price_info,
        }

    except Exception as e:
        logger.error(f"Price fetch failed for card {card_id}: {e}")
        return {'success': False, 'message': str(e)}


def batch_fetch_all():
    """
    Fetch prices for ALL cards in the database that have a name set.

    Returns:
        Summary dict with success/fail counts.
    """
    import sqlite3
    conn = sqlite3.connect(config.DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT id FROM cards WHERE name != '' ORDER BY id").fetchall()
    conn.close()

    total = len(rows)
    success_count = 0
    fail_count = 0
    results = []

    print(f"\n{'='*50}")
    print(f"Batch fetching prices for {total} cards...")
    print(f"{'='*50}\n")

    for i, row in enumerate(rows):
        card_id = row['id']
        result = fetch_price_for_card(card_id)

        if result.get('success'):
            success_count += 1
            price_str = ''
            if result.get('price_cny'):
                price_str = f" ~ \u00a5{result['price_cny']}"
            print(f"  [{i+1}/{total}] OK: {result.get('card_name','?')} -> {result.get('matched','?')}{price_str}")
        else:
            fail_count += 1
            print(f"  [{i+1}/{total}] SKIP: {result.get('card_name','?')} -> {result.get('message','?')}")

        results.append(result)

        # Rate limiting: respect TCG API limits
        time.sleep(2.5)  # ~24 requests per minute (under the 30/min limit)

    summary = {
        'total': total,
        'success': success_count,
        'failed': fail_count,
        'results': results,
    }

    print(f"\n{'='*50}")
    print(f"Done! Success: {success_count}, Failed: {fail_count}, Total: {total}")
    print(f"{'='*50}\n")

    return summary


def batch_fetch_unpriced():
    """Fetch only for cards that don't have any price records yet."""
    import sqlite3
    conn = sqlite3.connect(config.DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("""
        SELECT c.id, c.name
        FROM cards c
        LEFT JOIN price_records pr ON pr.card_id = c.id
        WHERE c.name != '' AND pr.id IS NULL
        ORDER BY c.id
    """).fetchall()
    conn.close()

    total = len(rows)
    if total == 0:
        print("All cards already have price records!")
        return {'total': 0, 'success': 0, 'failed': 0}

    print(f"\nFound {total} cards without price records. Starting fetch...\n")
    success_count = 0

    for i, row in enumerate(rows):
        result = fetch_price_for_card(row['id'])
        if result.get('success'):
            success_count += 1
            print(f"  [{i+1}/{total}] OK: {row['name']} -> \u00a5{result.get('price_cny','?')}")
        else:
            print(f"  [{i+1}/{total}] SKIP: {row['name']} -> {result.get('message','?')}")
        time.sleep(2.5)

    print(f"\nDone! Fetched prices for {success_count}/{total} cards.\n")
    return {'total': total, 'success': success_count, 'failed': total - success_count}


# ============ CLI Entry Point ============

if __name__ == '__main__':
    """Run as a standalone script for manual price fetching."""
    import sys
    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s [%(levelname)s] %(message)s')

    args = sys.argv[1:]

    if not args or '--help' in args or '-h' in args:
        print(__doc__)
        print("\nUsage:")
        print("  python scraper.py                    # Show help")
        print("  python scraper.py --search \"Pikachu VMAX\"  # Search TCG API")
        print("  python scraper.py --all              # Batch fetch all cards")
        print("  python scraper.py --unpriced          # Batch fetch only unpriced cards")
        print("  python scraper.py --id 5             # Fetch price for card ID 5")
        sys.exit(0)

    elif '--search' in args:
        idx = args.index('--search')
        query = args[idx + 1] if idx + 1 < len(args) else ''
        if query:
            results = search_tcg_cards(query)
            for r in results:
                print(f"\n  Name: {r['name']}")
                print(f"  Set:  {r['set_name']} #{r['number']}")
                print(f"  Rarity: {r['rarity']}")
                if r['usd_market_price']:
                    print(f"  TCGPlayer: ${r['usd_market_price']:.2f} (~\u00a5{r['cny_estimated_price']})")
                if r['eur_avg_price']:
                    print(f"  CardMarket: \u20ac{r['eur_avg_price']:.2f}")
                print(f"  Image: {r['image_large']}")
        else:
            print("Please provide a search query: --search \"card name\"")

    elif '--all' in args:
        batch_fetch_all()

    elif '--unpriced' in args:
        batch_fetch_unpriced()

    elif '--id' in args:
        idx = args.index('--id')
        card_id = int(args[idx + 1])
        result = fetch_price_for_card(card_id)
        print(json.dumps(result, indent=2, ensure_ascii=False))
