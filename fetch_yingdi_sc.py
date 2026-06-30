#!/usr/bin/env python3
"""
抓取旅法师营地的简体中文版宝可梦卡牌数据
策略：遍历已知 ID 范围，提取卡牌详情页数据
"""
import json
import re
import time
import urllib.request
import urllib.error

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'zh-CN,zh;q=0.9',
    'Referer': 'https://www.iyingdi.com/',
}

PROXY = 'http://127.0.0.1:7897'  # 你的代理地址

def fetch_url(url, timeout=15):
    """通过代理抓取 URL"""
    req = urllib.request.Request(url, headers=HEADERS)
    # Python urllib 支持 http 代理
    proxy_handler = urllib.request.ProxyHandler({'http': PROXY, 'https': PROXY})
    opener = urllib.request.build_opener(proxy_handler)
    try:
        with opener.open(req, timeout=timeout) as r:
            return r.read().decode('utf-8', errors='ignore')
    except Exception as e:
        print(f"  ❌ {url[-30:]}: {e}")
        return None

def parse_card_detail(html, card_id):
    """从详情页 HTML 提取卡牌数据"""
    data = {'id': card_id, 'tcg_id': f'yingdi-sc-{card_id}'}
    
    # 卡名
    m = re.search(r'content="([^"]+)卡牌详情', html)
    if m:
        data['name'] = m.group(1).strip()
    
    # 系列
    m = re.search(r'系列：([^<"]+)', html)
    if m:
        data['set_name'] = m.group(1).strip()
        
    # 类型（宝可梦/训练师/能量）
    m = re.search(r'类型：\s*([^<\n]+)', html)
    if m:
        data['card_type'] = m.group(1).strip()
        
    # 属性
    m = re.search(r'属性：\s*([^<\n]+)', html)
    if m:
        data['type'] = m.group(1).strip()
        
    # 稀有度
    m = re.search(r'稀有度：\s*([^<\n]+)', html)
    if m:
        data['rarity'] = m.group(1).strip()
        
    # 阶段
    m = re.search(r'阶段：\s*([^<\n]+)', html)
    if m:
        data['stage'] = m.group(1).strip()
        
    # HP
    m = re.search(r'HP[：:]\s*(\d+)', html)
    if m:
        data['hp'] = int(m.group(1))
        
    # 图片 URL
    m = re.search(r'og:image"\s*content="([^"]+)"', html)
    if m:
        data['image_url'] = m.group(1)
        
    return data

def scan_id_range(start_id, end_id):
    """扫描 ID 范围，找出所有简中卡"""
    print(f"🔍 扫描 ID 范围 {start_id} ~ {end_id}...")
    sc_ids = []
    
    for card_id in range(start_id, end_id + 1):
        url = f"https://www.iyingdi.com/tz/tool/general/pcards/{card_id}"
        html = fetch_url(url)
        
        if not html:
            continue
            
        # 检查是否是简中卡（页面有 系列： 且不是 404）
        if '系列：' in html and '卡牌详情' in html:
            sc_ids.append(card_id)
            if len(sc_ids) % 10 == 0:
                print(f"  已找到 {len(sc_ids)} 张简中卡...")
                
        time.sleep(0.2)  # 限速
        
    print(f"✅ 扫描完成，找到 {len(sc_ids)} 张简中卡")
    return sc_ids

def main():
    print("=" * 60)
    print("🚀 旅法师营地简中卡牌数据抓取")
    print("=" * 60)
    
    # 先扫描 ID 范围（根据之前的测试，简中卡 ID 在 27608 附近和 30000+）
    # 为了不扫太多，先测试一个较小的范围
    test_start = 27608
    test_end = 27700  # 先测 100 个 ID
    
    print(f"\n📊 第一阶段：扫描 ID 范围 {test_start}~{test_end}")
    sc_ids = scan_id_range(test_start, test_end)
    
    if not sc_ids:
        print("❌ 未找到任何简中卡，请扩大 ID 范围")
        return
        
    # 抓取详情
    print(f"\n📥 第二阶段：抓取 {len(sc_ids)} 张卡牌详情...")
    cards = []
    for card_id in sc_ids:
        url = f"https://www.iyingdi.com/tz/tool/general/pcards/{card_id}"
        html = fetch_url(url)
        if html:
            data = parse_card_detail(html, card_id)
            cards.append(data)
            print(f"  ✅ {data.get('name', '?')} ({data.get('set_name', '?')})")
            
    # 保存
    output = f"/Volumes/资料/workbuddy/kapai/backups/yingdi_sc_cards_{test_start}_{test_end}.json"
    with open(output, 'w', encoding='utf-8') as f:
        json.dump(cards, f, ensure_ascii=False, indent=2)
        
    print(f"\n✅ 抓取完成！共 {len(cards)} 张卡牌")
    print(f"   保存至：{output}")
    
    # 提示下一步
    print(f"\n💡 如需抓取更多卡牌，请修改脚本中的 test_start/test_end 变量")

if __name__ == '__main__':
    main()
