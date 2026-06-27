"""
卡牌数据采集管道 (Data Pipeline)
================================

标准化、可重复执行的卡牌数据获取流程，嵌入程序核心。

管道方法注册表（按 order 排序）:
  #1  manual_curated_cn   人工策展中文版热门卡牌数据集（集换社参考价）
  #2+ (预留)              后续有效抓取方法顺序注册

设计原则:
  - 幂等性: 重复执行同一方法不会产生重复数据（upsert 语义）
  - 可追溯: 每次执行记录到 pipeline_runs 表
  - 可预检: dry_run 模式只报告不写入
  - 可扩展: 新方法用 @register_method 装饰器注册即可

使用方法:
  # CLI
  python data_pipeline.py --list
  python data_pipeline.py --run manual_curated_cn
  python data_pipeline.py --run manual_curated_cn --dry-run
  python data_pipeline.py --run-all

  # 代码调用
  from data_pipeline import list_methods, run_method, run_all
  methods = list_methods()
  result = run_method('manual_curated_cn')
"""

import os
import json
import sqlite3
import logging
from datetime import datetime

from config import DATABASE_PATH
from db import get_db

logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_SOURCES_DIR = os.path.join(BASE_DIR, 'data', 'pipeline_sources')


# ============================================================
# 管道方法注册表
# ============================================================

_REGISTRY = {}


def register_method(order=99):
    """
    装饰器：注册一个管道方法。

    Args:
        order: 执行优先级（数字越小越先执行）

    被装饰的函数必须返回一个 dict，包含:
        id, name, description, source, version, run(dry_run=False) -> result
    或直接是一个符合接口的 dict。
    """
    def decorator(func):
        method_def = func()
        method_def['order'] = order
        method_def['_func_name'] = func.__name__
        _REGISTRY[method_def['id']] = method_def
        logger.debug(f"Registered pipeline method: {method_def['id']} (order={order})")
        return func
    return decorator


def list_methods():
    """列出所有已注册的管道方法，按 order 排序"""
    methods = sorted(_REGISTRY.values(), key=lambda m: m['order'])
    return [
        {
            'id': m['id'],
            'name': m['name'],
            'description': m['description'],
            'source': m['source'],
            'version': m['version'],
            'order': m['order'],
        }
        for m in methods
    ]


# ============================================================
# 执行历史记录
# ============================================================

def _ensure_pipeline_table():
    """确保 pipeline_runs 表存在"""
    conn = get_db()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS pipeline_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            method_id VARCHAR(50) NOT NULL,
            method_name VARCHAR(100) DEFAULT '',
            status VARCHAR(20) DEFAULT 'running',
            dry_run INTEGER DEFAULT 0,
            stats TEXT DEFAULT '{}',
            message TEXT DEFAULT '',
            started_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            finished_at DATETIME
        )
    ''')
    conn.commit()
    conn.close()


def _start_run(method_id, method_name, dry_run):
    """记录一次执行开始，返回 run_id"""
    _ensure_pipeline_table()
    conn = get_db()
    c = conn.cursor()
    c.execute('''
        INSERT INTO pipeline_runs (method_id, method_name, status, dry_run, started_at)
        VALUES (?, ?, 'running', ?, ?)
    ''', (method_id, method_name, 1 if dry_run else 0,
          datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
    run_id = c.lastrowid
    conn.commit()
    conn.close()
    return run_id


def _finish_run(run_id, status, stats, message=''):
    """记录一次执行结束"""
    conn = get_db()
    conn.execute('''
        UPDATE pipeline_runs
        SET status = ?, stats = ?, message = ?, finished_at = ?
        WHERE id = ?
    ''', (status, json.dumps(stats, ensure_ascii=False), message,
          datetime.now().strftime('%Y-%m-%d %H:%M:%S'), run_id))
    conn.commit()
    conn.close()


def get_run_history(limit=20):
    """获取最近的执行历史"""
    _ensure_pipeline_table()
    conn = get_db()
    rows = conn.execute(
        'SELECT * FROM pipeline_runs ORDER BY id DESC LIMIT ?',
        (limit,)
    ).fetchall()
    conn.close()
    result = []
    for r in rows:
        item = dict(r)
        try:
            item['stats'] = json.loads(item.get('stats') or '{}')
        except (json.JSONDecodeError, TypeError):
            item['stats'] = {}
        result.append(item)
    return result


# ============================================================
# 核心：执行引擎
# ============================================================

def run_method(method_id, dry_run=False):
    """
    执行指定的管道方法。

    Args:
        method_id: 方法唯一标识
        dry_run: True = 只预检不写入

    Returns:
        dict: 执行结果摘要
    """
    if method_id not in _REGISTRY:
        return {'success': False, 'message': f'未找到方法: {method_id}'}

    method = _REGISTRY[method_id]
    run_id = _start_run(method_id, method['name'], dry_run)

    print(f"\n{'='*60}")
    print(f"  管道执行: {method['name']} ({method_id})")
    print(f"  数据来源: {method['source']}")
    print(f"  模式: {'预检 (dry-run)' if dry_run else '正式执行'}")
    print(f"{'='*60}")

    try:
        result = method['run'](dry_run=dry_run)
        status = 'success' if result.get('success', True) else 'failed'
        _finish_run(run_id, status, result, result.get('message', ''))

        # 打印摘要
        print(f"\n  结果: {'成功' if result.get('success', True) else '失败'}")
        for k, v in result.items():
            if k != 'message' and k != 'success':
                print(f"  {k}: {v}")
        if result.get('message'):
            print(f"  说明: {result['message']}")
        print(f"{'='*60}\n")

        return result

    except Exception as e:
        logger.error(f"Pipeline method {method_id} failed: {e}", exc_info=True)
        _finish_run(run_id, 'error', {}, str(e))
        print(f"\n  执行出错: {e}\n{'='*60}\n")
        return {'success': False, 'message': str(e)}


def run_all(dry_run=False):
    """
    按 order 顺序执行所有已注册的管道方法。

    Returns:
        list: 每个方法的执行结果
    """
    methods = list_methods()
    print(f"\n准备执行 {len(methods)} 个管道方法...\n")

    results = []
    for m in methods:
        result = run_method(m['id'], dry_run=dry_run)
        results.append({'method_id': m['id'], 'method_name': m['name'], 'result': result})

    # 汇总
    success_count = sum(1 for r in results if r['result'].get('success', True))
    print(f"\n{'='*60}")
    print(f"  全部完成: {success_count}/{len(results)} 成功")
    print(f"{'='*60}\n")

    return results


# ============================================================
# 方法 #1: 人工策展中文版热门卡牌数据集
# ============================================================

@register_method(order=1)
def _define_manual_curated_cn():
    """
    方法 #1: 人工策展中文版热门卡牌数据集

    数据来源: 集换社/闲鱼公开市场行情参考价（2024-2025年）
    数据文件: data/pipeline_sources/manual_curated_cn.json

    执行逻辑:
      1. 加载 JSON 数据文件
      2. 逐条 upsert 到 card_catalog（按 name+set_name+card_number+rarity 去重）
      3. 对每张卡牌 upsert 价格记录到 price_records
      4. 同步更新 cards 表的 market_price
    """
    DATA_FILE = os.path.join(DATA_SOURCES_DIR, 'manual_curated_cn.json')

    def run(dry_run=False):
        # 1. 加载数据文件
        if not os.path.exists(DATA_FILE):
            return {'success': False, 'message': f'数据文件不存在: {DATA_FILE}'}

        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)

        cards = data.get('cards', [])
        if not cards:
            return {'success': False, 'message': '数据文件中没有卡牌数据'}

        price_platform = data.get('price_platform', '集换社')
        category = data.get('category', 'PTCG-SC')
        language = data.get('language', 'zh')
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        stats = {
            'total_in_file': len(cards),
            'inserted': 0,
            'updated': 0,
            'skipped': 0,
            'prices_added': 0,
            'prices_updated': 0,
            'cards_synced': 0,
        }

        if dry_run:
            # 预检模式：只统计不写入
            conn = get_db()
            for card in cards:
                existing = conn.execute(
                    'SELECT id FROM card_catalog WHERE name=? AND set_name=? AND card_number=? AND rarity=?',
                    (card['name'], card['set_name'], card['card_number'], card['rarity'])
                ).fetchone()
                if existing:
                    stats['updated'] += 1
                else:
                    stats['inserted'] += 1
            conn.close()
            stats['skipped'] = 0
            return {
                'success': True,
                'dry_run': True,
                **stats,
                'message': f'预检完成: 将插入 {stats["inserted"]} 张, 更新 {stats["updated"]} 张',
            }

        # 2. 正式执行：逐条 upsert
        conn = get_db()
        c = conn.cursor()

        for card in cards:
            # 检查是否已存在（name + set_name + card_number + rarity 四元组去重）
            existing = conn.execute(
                'SELECT id, market_price FROM card_catalog WHERE name=? AND set_name=? AND card_number=? AND rarity=?',
                (card['name'], card['set_name'], card['card_number'], card['rarity'])
            ).fetchone()

            if existing:
                # 更新现有记录
                catalog_id = existing['id']
                old_price = existing['market_price'] or 0
                new_price = card['market_price']

                c.execute('''
                    UPDATE card_catalog
                    SET name_en=?, set_code=?, hp=?, types=?, market_price=?,
                        category=?, language=?, updated_at=?
                    WHERE id=?
                ''', (card.get('name_en', ''), card.get('set_code', ''),
                      card.get('hp', ''), card.get('types', ''),
                      new_price, category, language, now, catalog_id))
                stats['updated'] += 1

                # 更新价格记录：检查今天是否已有该平台的价格记录
                today_price = conn.execute(
                    'SELECT id, price FROM price_records WHERE catalog_id=? AND platform=? AND recorded_at LIKE ?',
                    (catalog_id, price_platform, now[:10] + '%')
                ).fetchone()

                if today_price:
                    if today_price['price'] != new_price:
                        c.execute('UPDATE price_records SET price=? WHERE id=?',
                                  (new_price, today_price['id']))
                        stats['prices_updated'] += 1
                    else:
                        stats['skipped'] += 1
                else:
                    c.execute('''
                        INSERT INTO price_records (catalog_id, platform, price, currency, recorded_at)
                        VALUES (?, ?, ?, 'CNY', ?)
                    ''', (catalog_id, price_platform, new_price, now))
                    stats['prices_added'] += 1

            else:
                # 插入新记录
                c.execute('''
                    INSERT INTO card_catalog
                        (name, name_en, set_name, set_code, card_number, rarity,
                         hp, types, market_price, category, language, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (card['name'], card.get('name_en', ''), card['set_name'],
                      card.get('set_code', ''), card['card_number'], card['rarity'],
                      card.get('hp', ''), card.get('types', ''),
                      card['market_price'], category, language, now, now))
                catalog_id = c.lastrowid
                stats['inserted'] += 1

                # 插入价格记录
                c.execute('''
                    INSERT INTO price_records (catalog_id, platform, price, currency, recorded_at)
                    VALUES (?, ?, ?, 'CNY', ?)
                ''', (catalog_id, price_platform, card['market_price'], now))
                stats['prices_added'] += 1

        # 3. 同步更新 cards 表的 market_price
        synced = conn.execute('''
            UPDATE cards
            SET market_price = (
                SELECT cc.market_price FROM card_catalog cc
                WHERE cards.catalog_id = cc.id
            )
            WHERE catalog_id IS NOT NULL
              AND EXISTS (SELECT 1 FROM card_catalog WHERE id = cards.catalog_id)
        ''')
        stats['cards_synced'] = synced.rowcount

        conn.commit()
        conn.close()

        return {
            'success': True,
            **stats,
            'message': f'完成: 插入 {stats["inserted"]} 张, 更新 {stats["updated"]} 张, '
                       f'价格新增 {stats["prices_added"]} 条/更新 {stats["prices_updated"]} 条',
        }

    return {
        'id': 'manual_curated_cn',
        'name': '人工策展中文版热门卡牌数据集',
        'description': '从本地策展的 JSON 数据文件导入中文版热门卡牌及集换社参考价。'
                       '覆盖朱&紫、剑&盾、太阳&月亮系列。幂等执行，重复运行只更新价格不重复插入。',
        'source': '集换社/闲鱼公开市场行情参考价（2024-2025年），人工整理校验',
        'version': '1.0.0',
        'run': run,
    }


# ============================================================
# CLI 入口
# ============================================================

def _cli():
    import sys
    import argparse

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s'
    )

    parser = argparse.ArgumentParser(
        description='卡牌数据采集管道 - 标准化数据获取流程',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python data_pipeline.py --list
  python data_pipeline.py --run manual_curated_cn
  python data_pipeline.py --run manual_curated_cn --dry-run
  python data_pipeline.py --run-all
  python data_pipeline.py --history
        """
    )
    parser.add_argument('--list', action='store_true', help='列出所有已注册的管道方法')
    parser.add_argument('--run', metavar='METHOD_ID', help='执行指定的管道方法')
    parser.add_argument('--run-all', action='store_true', help='按顺序执行所有管道方法')
    parser.add_argument('--dry-run', action='store_true', help='预检模式（只报告不写入）')
    parser.add_argument('--history', action='store_true', help='查看最近的执行历史')

    args = parser.parse_args()

    if args.list or (not args.run and not args.run_all and not args.history):
        methods = list_methods()
        print(f"\n已注册 {len(methods)} 个管道方法:\n")
        print(f"  {'#':<4} {'ID':<25} {'名称':<30} {'版本':<8} {'数据来源'}")
        print(f"  {'-'*100}")
        for m in methods:
            print(f"  {m['order']:<4} {m['id']:<25} {m['name']:<30} {m['version']:<8} {m['source'][:40]}")
        print()
        return

    if args.history:
        history = get_run_history(limit=20)
        if not history:
            print("\n暂无执行历史\n")
            return
        print(f"\n最近 {len(history)} 次执行记录:\n")
        print(f"  {'ID':<5} {'方法':<25} {'状态':<10} {'预检':<5} {'开始时间':<20} {'说明'}")
        print(f"  {'-'*100}")
        for h in history:
            dry = '是' if h['dry_run'] else '否'
            msg = (h.get('message') or '')[:40]
            print(f"  {h['id']:<5} {h['method_id']:<25} {h['status']:<10} {dry:<5} {h['started_at']:<20} {msg}")
        print()
        return

    if args.run:
        result = run_method(args.run, dry_run=args.dry_run)
        if not result.get('success'):
            sys.exit(1)
        return

    if args.run_all:
        results = run_all(dry_run=args.dry_run)
        failed = [r for r in results if not r['result'].get('success', True)]
        if failed:
            sys.exit(1)
        return


if __name__ == '__main__':
    _cli()
