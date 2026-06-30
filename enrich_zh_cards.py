#!/usr/bin/env python3
"""
补充简体中文卡牌的图片 URL 和详细信息
策略: PokeAPI(名称映射) → Pokemon TCG API(name+number 精确匹配) → 图片URL

使用方法:
  python3 enrich_zh_cards.py          # 处理所有缺少图片的记录
  python3 enrich_zh_cards.py --dry    # 只测试不写入
  python3 enrich_zh_cards.py --limit 10  # 只处理前N个唯一卡名
"""

import json, requests, time, os, os.path as op, sys, argparse

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://your-project.supabase.co")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")
TCG_API_KEY = os.environ.get("TCG_API_KEY", "")

SUPABASE_HEADERS = {
    "apikey": SUPABASE_SERVICE_KEY,
    "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
    "Content-Type": "application/json",
}

CACHE_DIR = op.expanduser("~/.cache/pokedex")
MAP_FILE = op.join(CACHE_DIR, "cn_en_names.json")
MATCH_CACHE_FILE = op.join(CACHE_DIR, "tcg_match_cache.json")

# ============ 帮助函数 ============

def load_name_map():
    with open(MAP_FILE) as f:
        raw = json.load(f)
    # 建立两种索引: dex→names, cn→en
    by_dex = {}
    by_cn = {}
    for dex, names in raw.items():
        by_dex[int(dex)] = names
        by_cn[names["cn"]] = names["en"]
    return by_dex, by_cn


def get_en_name(details, by_dex, by_cn):
    """中文卡牌名 → 英文名"""
    cn = details.get("cardName", "")
    dex = details.get("pokedexCode")
    
    # 训练家卡/能量卡等直接翻译
    DIRECT = {
        "基本草能量": "Grass Energy", "基本火能量": "Fire Energy",
        "基本水能量": "Water Energy", "基本雷能量": "Lightning Energy",
        "基本超能量": "Psychic Energy", "基本斗能量": "Fighting Energy",
        "基本恶能量": "Darkness Energy", "基本钢能量": "Metal Energy",
        "基本妖能量": "Fairy Energy",
        "博士的研究": "Professor's Research", "博士的研究(红豆杉博士)": "Professor's Research",
        "裁判": "Judge", "玛俐": "Marnie", "老大的指令": "Boss's Orders",
        "宝可装置3.0": "Pokégear 3.0",
    }
    if cn in DIRECT:
        return DIRECT[cn]
    
    # 通过图鉴编号
    base_en = None
    if dex and int(dex) in by_dex:
        base_en = by_dex[int(dex)]["en"].capitalize()
    else:
        # 通过中文名前缀匹配
        best_len = 0
        for cname, ename in by_cn.items():
            if cn.startswith(cname) and len(cname) > best_len:
                base_en = ename.capitalize()
                best_len = len(cname)
    
    if not base_en:
        # 最后尝试：直接搜索 Pokemon TCG API 看能否找到
        return cn  # 返回中文名作为最后手段
    
    # 处理后缀 (V/VMAX/GX/ex 等)
    suffix = ""
    for cname in by_cn:
        if cn.startswith(cname):
            remaining = cn[len(cname):].strip().upper()
            break
    else:
        remaining = cn.upper()
    
    for tag, en_tag in [("V-UNION", " V-UNION"), ("VSTAR", " VSTAR"),
                         ("VMAX", " VMAX"), ("GX", " GX"),
                         ("EX", " EX"), ("ex", " ex")]:
        if tag in remaining or tag.lower() in cn.lower():
            if "V" in remaining and tag != "V" and "V" in tag:
                suffix = f" {en_tag.strip()}"  # 避免 V 重复匹配
                break
            elif tag == "V" and any(t in remaining for t in ["VMAX", "VSTAR", "V-UNION"]):
                continue
            else:
                suffix = f" {en_tag.strip()}"
                break
    else:
        if "V" in remaining.replace("VSTAR", "").replace("VMAX", "").replace("V-UNION", ""):
            suffix = " V"
    
    return base_en + suffix


def query_tcg_api(params, cache):
    """查询 Pokemon TCG API（带缓存）"""
    key = json.dumps(params, sort_keys=True)
    if key in cache:
        return cache[key]
    
    try:
        resp = requests.get(
            "https://api.pokemontcg.io/v2/cards",
            params={**params, "pageSize": 5},
            headers={"X-Api-Key": TCG_API_KEY},
            timeout=20
        )
        if resp.status_code == 200:
            result = resp.json().get("data", [])
            cache[key] = result
            return result
    except:
        pass
    cache[key] = []
    return []


def match_card(en_name, card_number, match_cache):
    """精确匹配卡牌：先按 name+number，降级到仅 name"""
    cn_int = None
    if card_number:
        try:
            cn_int = int(str(card_number).split("/")[0])
        except:
            pass
    
    # 策略1: name + number 精确匹配
    if cn_int:
        results = query_tcg_api(
            {"q": f'name:"{en_name}" number:"{cn_int}"'},
            match_cache
        )
        if results:
            return results[0]
    
    # 策略2: 仅 name 搜索，再按 number 过滤
    results = query_tcg_api({"q": f'name:"{en_name}"'}, match_cache)
    if not results:
        return None
    
    if cn_int:
        for c in results:
            try:
                if int(c.get("number", "0")) == cn_int:
                    return c
            except:
                pass
        # 找最接近的
        best, best_diff = None, 99
        for c in results:
            try:
                diff = abs(int(c.get("number", "999")) - cn_int)
                if diff < best_diff:
                    best_diff, best = diff, c
            except:
                pass
        if best_diff <= 3:
            return best
    
    return results[0]


def paginate_supabase(table, params, page_size=1000):
    all_rows = []
    offset = 0
    while True:
        p = dict(params)
        p["offset"] = offset
        p["limit"] = page_size
        resp = requests.get(f"{SUPABASE_URL}/rest/v1/{table}",
                          headers=SUPABASE_HEADERS, params=p)
        if resp.status_code != 200:
            break
        batch = resp.json()
        all_rows.extend(batch)
        if len(batch) < page_size:
            break
        offset += page_size
    return all_rows


def update_card(card_id, data, dry_run):
    if dry_run:
        return True
    try:
        resp = requests.patch(
            f"{SUPABASE_URL}/rest/v1/card_catalog",
            headers=SUPABASE_HEADERS,
            params={"id": f"eq.{card_id}"},
            json=data
        )
        return resp.status_code in (200, 204)
    except:
        return False


# ============ 主流程 ============

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry", action="store_true", help="只测试不写入")
    parser.add_argument("--limit", type=int, default=0, help="只处理前N个唯一卡名")
    parser.add_argument("--continue-from", type=int, default=0, help="从第N个卡名继续")
    args = parser.parse_args()
    
    # 1. 加载名称映射
    by_dex, by_cn = load_name_map()
    print(f"📖 名称映射: {len(by_dex)} 个图鉴编号, {len(by_cn)} 个中文名")
    
    # 2. 加载 CrystMiku 数据
    with open('/Volumes/资料/workbuddy/kapai/ptcg_cards_chs.json', 'r', encoding='utf-8') as f:
        chs_data = json.load(f)
    
    # 建立 中文卡名→详情 索引
    chs_idx = {}
    for s in chs_data:
        for c in s.get("cards", []):
            d = c.get("details", {})
            cn = d.get("cardName", "")
            if cn and cn not in chs_idx:
                chs_idx[cn] = d
    print(f"📦 CrystMiku 卡名索引: {len(chs_idx)} 个唯一名称")
    
    # 3. 加载匹配缓存
    match_cache = {}
    if op.exists(MATCH_CACHE_FILE):
        with open(MATCH_CACHE_FILE) as f:
            match_cache = json.load(f)
        print(f"💾 匹配缓存: {len(match_cache)} 条")
    
    # 4. 获取需要补充的记录
    print("\n📊 获取缺失图片的记录...")
    missing = paginate_supabase("card_catalog", {
        "select": "id,name,card_number,image_url,rarity,hp,artist,types,set_name",
        "language": "eq.zh",
        "image_url": "is.null"
    })
    
    # 去重：按唯一卡名
    seen = set()
    unique = []
    for rec in missing:
        cn = rec.get("name", "")
        if cn not in seen:
            seen.add(cn)
            unique.append(rec)
    
    if args.continue_from > 0:
        unique = unique[args.continue_from:]
    if args.limit > 0:
        unique = unique[:args.limit]
    
    print(f"  共 {len(missing)} 条记录 ({len(unique)} 个唯一卡名)")
    print(f"  处理范围: {'前' + str(args.limit) + '个' if args.limit else '全部'}")
    
    # 5. 逐卡名处理
    stats = {"img_ok": 0, "no_match": 0, "no_en": 0, "errors": 0}
    start_time = time.time()
    
    print(f"\n🔄 开始补充...")
    for i, rec in enumerate(unique):
        cn_name = rec.get("name", "")
        card_id = rec.get("id")
        card_num = rec.get("card_number", "")
        
        # 从 CrystMiku 获取详情
        details = chs_idx.get(cn_name)
        if not details:
            for cn, d in chs_idx.items():
                if cn_name in cn or cn in cn_name:
                    details = d
                    break
        if not details:
            stats["no_match"] += 1
            continue
        
        # 获取英文名
        en_name = get_en_name(details, by_dex, by_cn)
        if not en_name:
            stats["no_en"] += 1
            continue
        
        # 精确匹配
        matched = match_card(en_name, card_num, match_cache)
        if not matched:
            stats["no_match"] += 1
            continue
        
        # 提取数据
        images = matched.get("images", {})
        image_url = images.get("small") or images.get("large") or ""
        
        if not image_url:
            stats["no_match"] += 1
            continue
        
        update_data = {"image_url": image_url}
        if matched.get("hp") and not rec.get("hp"):
            update_data["hp"] = str(matched["hp"])
        if matched.get("artist") and not rec.get("artist"):
            update_data["artist"] = matched["artist"]
        if matched.get("types") and not rec.get("types"):
            update_data["types"] = matched["types"]
        if matched.get("rarity") and not rec.get("rarity"):
            update_data["rarity"] = matched["rarity"]
        
        # 更新 Supabase
        if update_card(card_id, update_data, args.dry):
            stats["img_ok"] += 1
        
        # 进度输出
        if (i + 1) % 50 == 0:
            elapsed = time.time() - start_time
            rate = (i + 1) / elapsed if elapsed > 0 else 0
            eta = (len(unique) - i - 1) / rate if rate > 0 else 0
            print(f"  [{i+1}/{len(unique)}] ✅{stats['img_ok']} ❌{stats['no_match']} ⚠️{stats['no_en']} "
                  f"| {rate:.1f}/s | ETA: {eta:.0f}s")
            if not args.dry:
                with open(MATCH_CACHE_FILE, "w") as f:
                    json.dump(match_cache, f)
        
        time.sleep(0.04)  # API 速率限制 (约 25 req/s)
    
    # 保存缓存
    if not args.dry:
        with open(MATCH_CACHE_FILE, "w") as f:
            json.dump(match_cache, f)
    
    elapsed = time.time() - start_time
    print(f"\n{'='*50}")
    print(f"✅ 完成！耗时 {elapsed:.1f}s")
    print(f"  图片更新成功: {stats['img_ok']}")
    print(f"  未找到匹配:   {stats['no_match']}")
    print(f"  无英文名:     {stats['no_en']}")
    print(f"  错误:         {stats['errors']}")
    print(f"  命中率:       {stats['img_ok']/max(stats['img_ok']+stats['no_match']+stats['no_en'],1)*100:.1f}%")
    if args.dry:
        print(f"\n⚠️  DRY RUN 模式 - 未实际写入数据库")


if __name__ == "__main__":
    main()
