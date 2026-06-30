#!/usr/bin/env python3
"""测试 Pokemon TCG API 和 Supabase 连接"""
import json
import urllib.request
import urllib.parse

# 测试 Pokemon TCG API
print("测试 Pokemon TCG API...")
url = "https://api.pokemontcg.io/v2/cards?pageSize=2"
req = urllib.request.Request(url)
req.add_header("User-Agent", "PokemonCardsManager/1.0")

try:
    with urllib.request.urlopen(req, timeout=10) as response:
        data = json.loads(response.read().decode('utf-8'))
        print(f"✅ API 连接成功! 总共有 {data.get('totalCount', 0)} 张卡")
        if data.get('data'):
            card = data['data'][0]
            print(f"   示例卡牌: {card['name']} ({card['id']})")
            print(f"   图片: {card['images']['large']}")
except Exception as e:
    print(f"❌ API 连接失败: {e}")

print()

# 测试 Supabase 连接
print("测试 Supabase 连接...")
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://your-project.supabase.co")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")

url2 = f"{SUPABASE_URL}/rest/v1/card_catalog?select=id,tcg_id&limit=2"
headers = {
    "apikey": SUPABASE_SERVICE_KEY,
    "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}"
}
req2 = urllib.request.Request(url2, headers=headers)

try:
    with urllib.request.urlopen(req2, timeout=10) as response:
        data2 = json.loads(response.read().decode('utf-8'))
        print(f"✅ Supabase 连接成功! 获取到 {len(data2)} 条数据")
        print(f"   示例: {data2}")
except Exception as e:
    print(f"❌ Supabase 连接失败: {e}")
