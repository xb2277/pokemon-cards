# 数据采集管道标准化 — 完成报告

## 完成内容

将"人工策展中文版卡牌数据"这一成功方法，标准化为**可重复执行的数据管道**，嵌入程序核心。

### 新增文件

| 文件 | 说明 |
|------|------|
| `data_pipeline.py` | 数据管道核心模块（注册表 + 执行引擎 + CLI） |
| `data/pipeline_sources/manual_curated_cn.json` | 方法#1的数据文件（59张中文版卡牌） |

### 修改文件

| 文件 | 变更 |
|------|------|
| `db.py` | 新增 `pipeline_runs` 表 + `card_catalog` 的 market_price/category/language 列迁移 |
| `app.py` | 新增 4 个管道管理 API（管理员权限） |

## 管道架构

```
data_pipeline.py
├── @register_method(order=1)  ← 装饰器注册新方法
│   └── manual_curated_cn      ← 方法#1：人工策展中文版卡牌
├── run_method(id, dry_run)    ← 执行单个方法（幂等）
├── run_all(dry_run)           ← 按顺序执行所有方法
├── get_run_history()          ← 查看执行历史
└── _ensure_pipeline_table()   ← 自动建表

data/pipeline_sources/
└── manual_curated_cn.json     ← 方法#1的数据源文件
```

### 方法接口标准

每个管道方法实现统一接口：
- `id` — 唯一标识
- `name` — 中文名称
- `description` — 功能描述
- `source` — 数据来源
- `version` — 版本号
- `order` — 执行优先级（数字越小越先）
- `run(dry_run=False)` — 执行函数，返回统计摘要

### 幂等性保证

- 卡牌去重：`name + set_name + card_number + rarity` 四元组
- 价格去重：同一天同一平台不重复插入
- 重复执行只更新元数据和价格，不产生重复记录

### 双入口

**CLI:**
```bash
python data_pipeline.py --list                              # 列出方法
python data_pipeline.py --run manual_curated_cn             # 执行方法
python data_pipeline.py --run manual_curated_cn --dry-run   # 预检
python data_pipeline.py --run-all                           # 执行全部
python data_pipeline.py --history                           # 查看历史
```

**API (管理员权限):**
```
GET  /api/pipeline/methods     — 列出方法
POST /api/pipeline/run         — 执行方法 {method_id, dry_run}
POST /api/pipeline/run-all     — 执行全部 {dry_run}
GET  /api/pipeline/history     — 执行历史
```

## 验证结果

- dry-run 预检：59张全部识别为"待更新"
- 正式执行：0插入 / 59更新 / 59价格跳过 / 11用户卡牌同步
- 二次执行：完全幂等，0重复
- 执行历史：3条记录正确写入 pipeline_runs 表
- 数据完整性：72张卡牌、72条价格、0重复

## 后续扩展

发现新的有效数据抓取方法时，只需：
1. 准备数据文件（如需）放入 `data/pipeline_sources/`
2. 在 `data_pipeline.py` 中用 `@register_method(order=N)` 注册新方法
3. 实现 `run(dry_run)` 函数即可自动纳入管道
