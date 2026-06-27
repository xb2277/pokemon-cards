"""
定时任务 - 每天0点自动抓取卡牌数据和价格

使用方法：
1. 系统 cron 任务（推荐）：
   0 0 * * * cd /path/to/kapai && python3 scheduler.py run >> logs/scheduler.log 2>&1

2. 或者直接运行（测试用）：
   python3 scheduler.py run

功能：
1. 抓取所有 card_catalog 卡牌的完整信息（hp, types, attacks, 价格等）
2. 更新 card_catalog 表
3. 更新 price_records 表
4. 同步更新用户卡牌的 market_price（用于资产看板）
5. 生成每日快照（snapshots 表）
"""

import sys
import logging
from datetime import datetime

# Add current directory to path
import os
os.chdir(os.path.dirname(os.path.abspath(__file__)))

from db import (
    get_all_catalog, get_all_cards, get_catalog_latest_price,
    update_card, take_snapshot, get_db, init_db
)
from price_fetcher import fetch_catalog_price, fetch_all_catalog_prices

# Configure logging
# Ensure logs directory exists BEFORE setting up logging
os.makedirs('logs', exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('logs/scheduler.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)


def update_all_market_prices():
    """
    Update market_price for all user cards based on latest catalog prices.
    This ensures the dashboard shows accurate valuations.
    """
    from db import get_all_cards, get_catalog_latest_price, update_card
    
    cards = get_all_cards()
    updated = 0
    failed = 0
    
    logger.info(f"开始更新 {len(cards)} 张用户卡牌的市场价格...")
    
    for card in cards:
        if not card.get('catalog_id'):
            continue
        
        try:
            latest = get_catalog_latest_price(card['catalog_id'])
            if latest and latest.get('avg'):
                update_card(card['id'], {'market_price': latest['avg']})
                updated += 1
        except Exception as e:
            logger.error(f"更新卡牌 #{card['id']} 失败: {e}")
            failed += 1
    
    logger.info(f"市场价格更新完成! 成功: {updated}, 失败: {failed}")
    return updated


def run_daily_fetch():
    """
    Daily fetch task:
    1. Fetch all catalog items' full info + prices from TCG API
    2. Update card_catalog table
    3. Update price_records table
    4. Update user cards' market_price
    5. Take daily snapshot
    """
    logger.info("="*60)
    logger.info(f"开始每日数据抓取任务 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("="*60)
    
    try:
        # Step 1: Fetch all catalog items (full info + prices)
        logger.info("\n[1/4] 抓取卡牌数据和价格...")
        result = fetch_all_catalog_prices(source='tcg')
        logger.info(f"抓取完成: 成功 {result['success']}/{result['total']}")
        
        # Step 2: Update user cards' market_price
        logger.info("\n[2/4] 更新用户卡牌市场价格...")
        updated = update_all_market_prices()
        
        # Step 3: Take daily snapshot
        logger.info("\n[3/4] 生成每日快照...")
        try:
            take_snapshot()
            logger.info("快照生成成功")
        except Exception as e:
            logger.error(f"快照生成失败: {e}")
        
        # Step 4: Print summary
        logger.info("\n" + "="*60)
        logger.info("每日抓取任务完成!")
        logger.info(f"  抓取: {result['success']}/{result['total']} 张卡牌")
        logger.info(f"  更新: {updated} 张卡牌市场价格")
        logger.info("="*60 + "\n")
        
        return True
        
    except Exception as e:
        logger.error(f"每日抓取任务失败: {e}", exc_info=True)
        return False


def setup_cron():
    """
    Setup system cron job (Linux/macOS).
    This function prints the cron command for manual setup.
    """
    script_path = os.path.abspath(__file__)
    work_dir = os.path.dirname(script_path)
    
    cron_cmd = f"0 0 * * * cd {work_dir} && python3 {script_path} run >> {work_dir}/logs/scheduler.log 2>&1"
    
    print("\n" + "="*60)
    print("定时任务设置说明")
    print("="*60)
    print(f"\n1. 添加以下 cron 任务（每天0点运行）:\n")
    print(f"   {cron_cmd}\n")
    print(f"2. 使用方法:")
    print(f"   crontab -e")
    print(f"   粘贴上面的命令，保存退出\n")
    print(f"3. 查看 cron 任务:")
    print(f"   crontab -l\n")
    print("="*60 + "\n")


if __name__ == '__main__':
    # Ensure logs directory exists
    os.makedirs('logs', exist_ok=True)
    
    # Initialize database (run migrations if needed)
    init_db()
    
    if len(sys.argv) > 1 and sys.argv[1] == 'run':
        # Run the daily fetch task
        success = run_daily_fetch()
        sys.exit(0 if success else 1)
    
    elif len(sys.argv) > 1 and sys.argv[1] == 'cron':
        # Print cron setup instructions
        setup_cron()
    
    elif len(sys.argv) > 1 and sys.argv[1] == 'update-prices':
        # Only update market prices (no fetching)
        update_all_market_prices()
    
    else:
        print("\n使用方法:")
        print("  python3 scheduler.py run            # 运行每日抓取任务")
        print("  python3 scheduler.py update-prices # 仅更新市场价格")
        print("  python3 scheduler.py cron           # 查看 cron 设置说明\n")
        print("定时任务（每天0点自动运行）:")
        print("  0 0 * * * cd /path/to/kapai && python3 scheduler.py run >> logs/scheduler.log 2>&1\n")
