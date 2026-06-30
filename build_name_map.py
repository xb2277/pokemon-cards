#!/usr/bin/env python3
"""构建中文宝可梦名称 → 英文名称映射（通过 PokeAPI）"""
import json, requests, time, os, os.path as op

PROXY = {"http": "http://127.0.0.1:7897", "https": "http://127.0.0.1:7897"}
CACHE_DIR = op.expanduser("~/.cache/pokedex")
os.makedirs(CACHE_DIR, exist_ok=True)
MAP_FILE = op.join(CACHE_DIR, "cn_en_names.json")

# 读取 CrystMiku 数据，提取所有 pokedexCode
with open('/Volumes/资料/workbuddy/kapai/ptcg_cards_chs.json', 'r', encoding='utf-8') as f:
    chs_data = json.load(f)

needed = sorted(set(
    c.get("details", {}).get("pokedexCode")
    for s in chs_data
    for c in s.get("cards", [])
    if c.get("details", {}).get("pokedexCode")
))

print(f"需要映射的图鉴编号: {len(needed)} 个 (范围 {min(needed)}~{max(needed)})")

# 加载已有缓存
cn_to_en = {}
if op.exists(MAP_FILE):
    with open(MAP_FILE) as f:
        cn_to_en = json.load(f)
    print(f"缓存已有: {len(cn_to_en)} 条")

missing = [d for d in needed if str(int(d)) not in cn_to_en]
print(f"需要获取: {len(missing)} 个")

if not missing:
    print("✅ 已经全部完成！")
else:
    for i, dex in enumerate(missing):
        try:
            resp = requests.get(
                f"https://pokeapi.co/api/v2/pokemon-species/{int(dex)}",
                proxies=PROXY, timeout=20
            )
            if resp.status_code == 200:
                data = resp.json()
                en_name = data.get("name", str(dex))
                # 查找中文名
                cn_name = None
                for entry in data.get("names", []):
                    lang = entry["language"]["name"]
                    if lang.startswith("zh"):  # zh-hant, zh-hans, zh-CN 等
                        cn_name = entry["name"]
                        break
                if not cn_name:
                    cn_name = en_name  # fallback to English
                
                cn_to_en[str(int(dex))] = {"cn": cn_name, "en": en_name}
            else:
                print(f"  ⚠️ #{dex}: HTTP {resp.status_code}")
        except Exception as e:
            print(f"  ⚠️ #{dex}: {e}")
        
        if (i + 1) % 30 == 0:
            print(f"  进度: {i+1}/{len(missing)} ({len(cn_to_en)} 条)")
            with open(MAP_FILE, "w") as f:
                json.dump(cn_to_en, f, ensure_ascii=False)
        
        time.sleep(0.06)  # 避免触发速率限制
    
    with open(MAP_FILE, "w") as f:
        json.dump(cn_to_en, f, ensure_ascii=False)

print(f"\n✅ 完成！共 {len(cn_to_en)} 条名称映射")
for dex, names in list(cn_to_en.items())[:15]:
    print(f"  #{dex}: {names['cn']} → {names['en']}")
