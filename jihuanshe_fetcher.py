"""
集换社价格抓取模块

通过模拟集换社 APP 的请求来获取卡牌价格数据。
集换社主要有：
1. 网站：jihuanshe.com（需登录，反爬强）
2. APP：可能有 API 接口
3. 微信小程序：可能有 API 接口

本模块尝试：
1. 模拟 APP API 请求（抓包分析）
2. 或者使用浏览器自动化访问网页版

使用方法：
    from jihuanshe_fetcher import fetch_jihuanshe_price
    price = fetch_jihuanshe_price('皮卡丘', '朱紫')
"""

import json
import logging
import re
import time
from datetime import datetime

import requests

from db import get_db

logger = logging.getLogger(__name__)

# 集换社可能的 API 端点（需通过抓包确认）
# 这些都是猜测，实际使用时需要通过 Charles/Fiddler 抓包获取
JHS_API_BASE = 'https://api.jihuanshe.com'  # 猜测
JHS_WEB_BASE = 'https://www.jihuanshe.com'

# 请求头（模拟手机 APP）
JHS_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148',
    'Accept': 'application/json',
    'Accept-Language': 'zh-CN,zh;q=0.9',
    'Content-Type': 'application/json',
}


def search_jhs_card(keyword, set_name=None):
    """
    搜索集换社卡牌
    
    Args:
        keyword: 卡牌名称（中文）
        set_name: 卡包名称（可选）
    
    Returns:
        List of card dicts with price info
    """
    # 尝试多个可能的 API 端点
    endpoints = [
        f'{JHS_API_BASE}/api/v1/card/search',
        f'{JHS_API_BASE}/api/card/list',
        f'{JHS_WEB_BASE}/api/card/search',
    ]
    
    for endpoint in endpoints:
        try:
            params = {'keyword': keyword, 'page': 1, 'pageSize': 10}
            if set_name:
                params['set'] = set_name
            
            resp = requests.get(
                endpoint,
                params=params,
                headers=JHS_HEADERS,
                timeout=10
            )
            
            if resp.status_code == 200:
                data = resp.json()
                logger.info(f"集换社搜索 '{keyword}' 成功: {len(data.get('data', []))} 条结果")
                return data.get('data', [])
            
        except Exception as e:
            logger.debug(f"端点 {endpoint} 失败: {e}")
            continue
    
    # 如果 API 都失败，尝试网页搜索（需要解析 HTML）
    logger.warning(f"集换社 API 搜索失败，尝试网页搜索: {keyword}")
    return _search_jhs_web(keyword, set_name)


def _search_jhs_web(keyword, set_name=None):
    """
    通过网页搜索集换社（解析 HTML）
    注意：集换社网页可能需要登录，且反爬较强
    """
    try:
        # 尝试访问集换社搜索页面
        search_url = f'{JHS_WEB_BASE}/search'
        params = {'q': keyword}
        
        resp = requests.get(
            search_url,
            params=params,
            headers=JHS_HEADERS,
            timeout=10
        )
        
        if resp.status_code != 200:
            logger.error(f"集换社网页搜索失败: HTTP {resp.status_code}")
            return []
        
        # 解析 HTML（这里需要根据实际页面结构调整）
        # 由于没有实际抓包，这里只是框架代码
        html = resp.text
        
        # 尝试从 HTML 中提取 JSON 数据（很多网站会把数据放在 <script> 标签里）
        json_match = re.search(r'window\.__INITIAL_STATE__\s*=\s*({.+?});', html)
        if json_match:
            data = json.loads(json_match.group(1))
            # 解析数据结构（根据实际调整）
            cards = data.get('searchResult', {}).get('items', [])
            return cards
        
        logger.warning("集换社网页搜索：无法解析页面数据")
        return []
        
    except Exception as e:
        logger.error(f"集换社网页搜索异常: {e}")
        return []


def fetch_jihuanshe_price(catalog_id):
    """
    从集换社抓取指定卡牌的价格
    
    Args:
        catalog_id: card_catalog 表的 ID
    
    Returns:
        Dict with price info
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
    name = catalog_item.get('name')
    set_name = catalog_item.get('set_name')
    
    # 搜索卡牌
    cards = search_jhs_card(name, set_name)
    
    if not cards:
        return {
            'success': False,
            'message': f'集换社未找到卡牌: {name}',
            'catalog_id': catalog_id
        }
    
    # 取第一个结果的价格
    card = cards[0]
    price = card.get('price') or card.get('avgPrice') or card.get('marketPrice')
    
    if not price:
        return {
            'success': False,
            'message': f'集换社未找到价格: {name}',
            'catalog_id': catalog_id
        }
    
    # 保存价格到数据库
    from db import add_catalog_price_record
    add_catalog_price_record(catalog_id, '集换社', float(price))
    
    logger.info(f"集换社价格抓取成功: {name} = ¥{price}")
    
    return {
        'success': True,
        'catalog_id': catalog_id,
        'catalog_name': name,
        'price': float(price),
        'platform': '集换社'
    }


def fetch_all_jihuanshe(limit=None):
    """
    批量抓取集换社价格
    """
    from db import get_all_catalog
    
    catalog, _ = get_all_catalog()
    
    if limit:
        catalog = catalog[:limit]
    
    total = len(catalog)
    success_count = 0
    fail_count = 0
    
    print(f"\n{'='*60}")
    print(f"开始抓取集换社价格: {total} 张卡牌")
    print(f"{'='*60}\n")
    
    for i, item in enumerate(catalog):
        print(f"[{i+1}/{total}] {item['name']} ... ", end='', flush=True)
        
        result = fetch_jihuanshe_price(item['id'])
        
        if result.get('success'):
            success_count += 1
            print(f"✓ ¥{result['price']}")
        else:
            fail_count += 1
            print(f"✗ {result.get('message', 'Unknown error')}")
        
        # 限速，避免被封
        if i < total - 1:
            time.sleep(3)
    
    print(f"\n{'='*60}")
    print(f"完成! 成功: {success_count}, 失败: {fail_count}, 总计: {total}")
    print(f"{'='*60}\n")
    
    return {
        'total': total,
        'success': success_count,
        'failed': fail_count,
    }


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s'
    )
    
    # 测试抓取
    print("集换社价格抓取模块")
    print("注意：本模块需要抓包获取实际的 API 端点")
    print("当前为框架代码，需要根据实际抓包结果完善\n")
    
    # 测试搜索（需要先抓包获取真实 API）
    # fetch_all_jihuanshe(limit=5)
