"""
集换社热门卡牌抓取脚本
使用 Playwright 渲染 JS 后抓取中文版宝可梦卡牌数据
"""
import sqlite3
import json
import time
import re
from datetime import datetime
from playwright.sync_api import sync_playwright

DB_PATH = 'cards.db'

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # 确保 card_catalog 有需要的字段
    cols = [row[1] for row in c.execute('PRAGMA table_info(card_catalog)').fetchall()]
    if 'language' not in cols:
        c.execute('ALTER TABLE card_catalog ADD COLUMN language TEXT DEFAULT "zh"')
    conn.commit()
    return conn

def scrape_jihuanshe():
    """用 Playwright 抓取集换社的热门卡牌数据"""
    results = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            locale='zh-CN',
            viewport={'width': 1280, 'height': 800},
        )

        # 监听网络请求，捕获 API 响应
        api_responses = []

        def handle_response(response):
            url = response.url
            if '/api/' in url or '/card' in url or '/market' in url:
                try:
                    content_type = response.headers.get('content-type', '')
                    if 'json' in content_type:
                        body = response.json()
                        api_responses.append({'url': url, 'data': body})
                        print(f'  [API捕获] {url}')
                except:
                    pass

        page = context.new_page()
        page.on('response', handle_response)

        # 1. 访问首页
        print('1. 访问集换社首页...')
        page.goto('https://www.jihuanshe.com', wait_until='networkidle', timeout=30000)
        time.sleep(3)
        print(f'   页面标题: {page.title()}')
        print(f'   当前URL: {page.url}')

        # 截取页面文本，看看有什么内容
        body_text = page.inner_text('body')
        print(f'   页面文本长度: {len(body_text)}')
        if body_text:
            print(f'   前500字: {body_text[:500]}')

        # 2. 尝试搜索"宝可梦"
        print('\n2. 尝试搜索宝可梦...')
        # 先看看页面上有没有搜索框
        inputs = page.query_selector_all('input')
        print(f'   找到 {len(inputs)} 个输入框')
        for i, inp in enumerate(inputs):
            placeholder = inp.get_attribute('placeholder') or ''
            input_type = inp.get_attribute('type') or ''
            print(f'   input[{i}]: type={input_type}, placeholder={placeholder}')

        # 3. 尝试直接访问可能的热门/列表页面
        print('\n3. 尝试访问卡牌列表页面...')
        test_paths = [
            'https://www.jihuanshe.com/card/list',
            'https://www.jihuanshe.com/market',
            'https://www.jihuanshe.com/hot',
            'https://www.jihuanshe.com/ptcg',
            'https://www.jihuanshe.com/#!cardList',
        ]

        for path in test_paths:
            try:
                print(f'\n   尝试: {path}')
                page.goto(path, wait_until='networkidle', timeout=15000)
                time.sleep(2)
                print(f'   最终URL: {page.url}')
                print(f'   页面标题: {page.title()}')
                text = page.inner_text('body')[:300]
                if text.strip():
                    print(f'   内容预览: {text}')
            except Exception as e:
                print(f'   失败: {e}')

        # 4. 检查捕获到的 API 响应
        print(f'\n4. 共捕获 {len(api_responses)} 个 API 响应')
        for resp in api_responses[:20]:
            url = resp['url']
            data = resp['data']
            data_str = json.dumps(data, ensure_ascii=False)[:200]
            print(f'   {url}')
            print(f'   数据: {data_str}')
            print()

        browser.close()

    return results

if __name__ == '__main__':
    print('=== 集换社热门卡牌抓取 ===\n')
    results = scrape_jihuanshe()
    print(f'\n共获取 {len(results)} 条卡牌数据')
