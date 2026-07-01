#!/usr/bin/env python3
"""
从旅法师营地 (iyingdi.com) 补充简体中文卡牌的图片 URL

营地收录了 4 个系列的中文卡图：
  cs2ac → 补充包 浓墨重彩 黎
  cs2bc → 补充包 浓墨重彩 靛
  cs4aC → 补充包 九彩汇聚 朋
  cs4bC → 补充包 九彩汇聚 源

图片 URL 格式: https://pic.iyingdi.com/pcards-card-import/yingdiimg/{abbr}/{num}.PNG

匹配规则: set_code + card_number 匹配 Supabase card_catalog 表

使用方法:
  python3 enrich_yingdi_zh.py --dry     # 只检查不写入
  python3 enrich_yingdi_zh.py           # 实际写入
"""

import json, requests, time, os, sys, argparse, gc

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")
if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
    print("请设置环境变量 SUPABASE_URL 和 SUPABASE_SERVICE_KEY")
    sys.exit(1)

# 代理
PROXY = os.environ.get("HTTPS_PROXY", os.environ.get("https_proxy", "http://127.0.0.1:7897"))
PROXIES = {"http": PROXY, "https": PROXY} if PROXY else {}

SUPABASE_HEADERS = {
    "apikey": SUPABASE_SERVICE_KEY,
    "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
    "Content-Type": "application/json",
}

# 营地 abbr → Supabase set_code (CrystMiku commodityCode)
YINGDI_SERIES = {
    "cs2ac": "CS2aC",   # 浓墨重彩 黎
    "cs2bc": "CS2bC",   # 浓墨重彩 靛
    "cs4aC": "CS4aC",   # 九彩汇聚 朋
    "cs4bC": "CS4bC",   # 九彩汇聚 源
}

YINGDI_BASE = "https://pic.iyingdi.com/pcards-card-import/yingdiimg"


def check_image_url(abbr, num):
    """HEAD 检查营地图片是否存在"""
    url = f"{YINGDI_BASE}/{abbr}/{num}.PNG"
    try:
        r = requests.head(url, timeout=8, proxies=PROXIES)
        if r.status_code == 200:
            return url, int(r.headers.get("Content-Length", 0))
    except:
        pass
    return None, 0


def process_series(abbr, set_code, card_map, dry_run):
    """处理单个系列：查询 → 验证 → 更新
    card_map: {card_number: num} (e.g. {"001/132": "1"})"""
    set_name_map = {
        "CS2aC": "浓墨重彩 黎", "CS2bC": "浓墨重彩 靛",
        "CS4aC": "九彩汇聚 朋", "CS4bC": "九彩汇聚 源",
    }
    set_name = set_name_map.get(set_code, set_code)

    # 查询这个系列的所有记录
    r = requests.get(
        f"{SUPABASE_URL}/rest/v1/card_catalog",
        headers={**SUPABASE_HEADERS, "Prefer": "count=exact"},
        params={"set_code": f"eq.{set_code}", "select": "id,name,set_code,card_number,image_url", "limit": 0},
    )
    total = int(r.headers.get("content-range", "0/0").split("/")[-1])
    if total == 0:
        print(f"  {set_name}: Supabase 中无记录")
        return 0, 0

    # 批量加载
    records = []
    for offset in range(0, total, 500):
        r = requests.get(
            f"{SUPABASE_URL}/rest/v1/card_catalog",
            headers=SUPABASE_HEADERS,
            params={
                "set_code": f"eq.{set_code}",
                "select": "id,name,set_code,card_number,image_url",
                "limit": 500, "offset": offset, "order": "id.asc",
            },
        )
        records.extend(r.json())

    # 匹配 + 更新
    ok, fail, skip = 0, 0, 0
    for i, rec in enumerate(records):
        num = card_map.get(rec["card_number"])
        if num is None:
            continue
        if rec.get("image_url"):
            skip += 1
            continue

        url = f"{YINGDI_BASE}/{abbr}/{num}.PNG"

        if dry_run:
            ok += 1
            if ok <= 3:
                print(f"  [DRY] #{rec['card_number']:>8s} {rec['name'][:15]} → {url}")
            continue

        try:
            r = requests.patch(
                f"{SUPABASE_URL}/rest/v1/card_catalog?id=eq.{rec['id']}",
                headers={**SUPABASE_HEADERS, "Prefer": "return=minimal"},
                json={"image_url": url},
            )
            if r.status_code in (200, 204):
                ok += 1
            else:
                fail += 1
        except Exception as e:
            fail += 1

        if (ok + fail) % 200 == 0:
            print(f"  ... {ok + fail} processed ok={ok} fail={fail}")

    # 释放内存
    del records
    gc.collect()

    print(f"  {set_name}: ✅{ok} ❌{fail} ⏭️{skip} (总数{total})")
    return ok, fail


def main():
    parser = argparse.ArgumentParser(description="从营地补充中文卡牌图片")
    parser.add_argument("--dry", action="store_true", help="只检查不写入")
    args = parser.parse_args()

    print("=== 营地中文卡牌图片补充 ===")
    print(f"涵盖系列: {len(YINGDI_SERIES)} 个")
    mode = "🔍 dry run" if args.dry else "✍️  正式写入"
    print(f"模式: {mode}\n")

    # 预加载 CrystMiku 卡牌数据
    with open("ptcg_cards_chs.json", "r") as f:
        cm_data = json.load(f)

    # 构建 set_code → card 映射 (只保留需要卡号→编号的映射)
    cm_card_map = {}  # set_code → {card_number: num}
    for series in cm_data:
        code = series.get("commodityCode", "")
        if code not in YINGDI_SERIES.values():
            continue
        cm_card_map[code] = {}
        for card in series.get("cards", []):
            details = card.get("details", {})
            cn = details.get("collectionNumber", "")
            if cn and "/" in cn:
                num = cn.split("/")[0].lstrip("0") or "0"
                cm_card_map[code][cn] = num
    del cm_data
    gc.collect()

    total_ok, total_fail = 0, 0
    for abbr, set_code in YINGDI_SERIES.items():
        ok, fail = process_series(abbr, set_code, cm_card_map.get(set_code, {}), args.dry)
        total_ok += ok
        total_fail += fail

    print(f"\n=== {'检查' if args.dry else '完成'} ===")
    print(f"  ✅ 成功: {total_ok}")
    print(f"  ❌ 失败: {total_fail}")
    print(f"  📊 中文卡总图: {total_ok + 583}/7603")


if __name__ == "__main__":
    main()
