# 宝可梦卡牌管理器 - 项目记忆

## 技术栈
- Flask + SQLite + Jinja2 模板 + 原生 JS（原版）
- 纯静态 HTML/JS + Supabase SDK（GitHub Pages 部署版）
- 管理员账号：admin / kapai2026
- 本地运行端口：5001

## 用户系统（2026-06-25 完成）
- 注册：邮箱 + 用户名 + 密码（`POST /api/auth/register`）
- 登录：邮箱（优先）或用户名（向后兼容）+ 密码（`POST /api/auth/web-login`）
- 微信绑定：为小程序预留（`POST /api/auth/bind-wechat`）
- 所有 API 使用 Bearer Token 认证
- users 表字段：id, openid, username, email, password_hash, nick_name, avatar, phone, role, token

## GitHub Pages 部署（2026-06-27 完成）
- 架构：纯静态 HTML/JS + Supabase（PostgreSQL + Auth + Storage）
- gh-pages 分支托管静态文件，GitHub Pages 自动部署
- 在线地址：https://xb2277.github.io/pokemon-cards/
- Supabase SDK 通过 CDN 加载（@supabase/supabase-js@2）
- 所有页面路径改为相对路径（./index.html, ./dashboard.html 等）
- supabase-config.js 中 SUPABASE_URL 和 SUPABASE_ANON_KEY 需替换为实际值
- schema.sql 定义了 PostgreSQL 表结构 + RLS 策略
- migrate_to_supabase.py 用于 SQLite → Supabase 数据迁移
- 本机代理端口：7897（git push 需用 -c http.proxy=http://127.0.0.1:7897）

## 待完成
- 用户需创建 Supabase 项目并运行 schema.sql
- 填写 supabase-config.js 中的实际密钥
- 运行 migrate_to_supabase.py 迁移数据
- Supabase Edge Function 实现价格抓取（Phase 2）
- Supabase cron 实现定时快照（Phase 2）
