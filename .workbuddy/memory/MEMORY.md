# 宝可梦卡牌管理器 - 项目记忆

## 技术栈
- Flask + SQLite + Jinja2 模板 + 原生 JS
- 管理员账号：admin / kapai2026
- 本地运行端口：5001

## 用户系统（2026-06-25 完成）
- 注册：邮箱 + 用户名 + 密码（`POST /api/auth/register`）
- 登录：邮箱（优先）或用户名（向后兼容）+ 密码（`POST /api/auth/web-login`）
- 微信绑定：为小程序预留（`POST /api/auth/bind-wechat`）
- 所有 API 使用 Bearer Token 认证
- users 表字段：id, openid, username, email, password_hash, nick_name, avatar, phone, role, token

## 卡牌数据库（2026-06-27 重建）
- card_catalog: 72 张中文版卡牌（简体中文 PTCG）
- 覆盖系列：朱&紫、剑&盾、太阳&月亮
- 价格来源：集换社参考价（CNY），存于 price_records 表
- cards 表通过 catalog_id 关联 card_catalog
- 集换社 API（api.jihuanshe.com）需 APP 端 token，无法直接抓取
- TCG API 仅有美版卡牌，不适合中文版卡牌管理
- Playwright 已安装在 kapai-env 中，可用于浏览器自动化

## 数据采集管道（2026-06-27 建立）
- 核心模块：`data_pipeline.py`，管道注册表 + 幂等执行 + 历史追踪
- 方法 #1：`manual_curated_cn` — 人工策展中文版卡牌数据集（集换社参考价）
  - 数据文件：`data/pipeline_sources/manual_curated_cn.json`
  - 后续有效抓取方法用 `@register_method(order=N)` 顺序注册
- CLI：`python data_pipeline.py --list/--run/--run-all/--history`
- API：`/api/pipeline/methods|run|run-all|history`（管理员权限）
- 执行历史表：`pipeline_runs`

## 部署
- Railway 部署多次尝试未成功（平台 502），搁置中
- 可考虑 Render / Vercel 静态 + API 分离方案
