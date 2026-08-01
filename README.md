# 时间预算学习追踪器

一套基于 Vue 3、Vite、FastAPI 与 PostgreSQL 的学习任务和时间预算管理软件。

## 已实现功能

- 账户注册、登录、个人资料、时区与可搜索性设置
- 无限层级学习任务、状态流转、时间预算与 80% / 100% / 150% 提醒
- 开始、暂停、恢复和结束学习计时；父任务汇总所有子任务实际时长
- 每日计划、长期任务引用、临时事项、完成进度与连续打卡
- 日期范围统计、每日趋势、任务投入分布与预算偏差
- 用户搜索、伙伴邀请、接受/拒绝、解除伙伴、屏蔽与取消屏蔽
- 伙伴计划分享，可独立决定是否公开计划/实际时长
- 固定选项鼓励、持久化通知和 WebSocket 实时推送
- 计时、任务和每日计划的 IndexedDB 离线保存与联网自动重放
- PostgreSQL 行级安全策略、跨所有者约束和 Alembic 数据库迁移

软件没有自由聊天、公开动态、排行榜或需求文档之外的社交功能。

## 技术结构

```text
frontend/               Vue 3 + Vite + TypeScript + Pinia + Dexie
backend/                FastAPI + SQLAlchemy Async + Pydantic
backend/migrations/     Alembic + PostgreSQL RLS / 完整性触发器
backend/tests/          SQLite API 回归测试
docs/                   架构、数据库、离线同步、API 与部署文档
compose.yaml            本地开发 PostgreSQL
compose.production.yaml 完整生产容器编排
```

## 快速启动

完整步骤见 [部署教程](docs/deployment.md)。

```powershell
# 1. 启动本地 PostgreSQL
docker compose up -d postgres

# 2. 后端（新终端）
cd backend
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
Copy-Item .env.example .env
alembic upgrade head
uvicorn app.main:app --reload

# 3. 前端（新终端）
cd frontend
corepack enable
pnpm install
Copy-Item .env.example .env
pnpm dev
```

打开 `http://localhost:5173`。

## 验证

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\ruff.exe check app tests migrations

cd ..\frontend
pnpm run type-check
pnpm run build
```

## 文档

- [整体架构](docs/architecture.md)
- [数据库结构](docs/database-schema.md)
- [API 清单](docs/api.md)
- [离线同步](docs/offline-sync.md)
- [部署教程](docs/deployment.md)
