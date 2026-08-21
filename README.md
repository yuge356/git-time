# DayFlow

一套基于 Vue 3、Vite、FastAPI 与 PostgreSQL 的项目、任务和时间管理软件。

## 已实现功能

- Supabase Auth 邮箱/手机号 + 密码注册登录；手机号注册根据访问 IP 预选国家区号（默认 `+86`）并可手动更换，在应用层映射为内部邮箱身份，MVP 不接入短信服务
- Supabase 托管 PostgreSQL 保存用户资料、项目、计时与统计源数据
- 中文界面的操作成功、失败、网络及本地存储提醒统一使用中文，错误翻译集中管理以便后续扩展英文版
- 未登录访问根地址时显示响应式欢迎页；首张轮播使用横向任务树动效演示叶子任务、时间预算和项目进度自下而上汇聚，后续轮播展示真实的今日任务、时间统计与项目界面
- 紫白左右分栏中文登录卡片，登录与注册在同一页面内切换，包含浅灰输入框、眼睛图标密码显隐控制、锁图标字段标识、忘记密码提示与响应式布局
- 新注册用户首次登录显示分步使用指引；完成或跳过后写入 Supabase 用户元数据，老用户不受影响
- DayFlow 品牌字标与大号紫底白字 DF Logo，字母使用华文琥珀字体并保持适中间距
- “项目 / 课程 → 模块 / 任务 → 可执行任务（可再含一层子任务）”灵活任务树，整体采用 Apple Liquid Glass 风格结合 2.5D 扁平化设计；背景使用柔和的冷灰与冰蓝渐变环境光晕，中央毛玻璃卡片（严格圆角矩形）具备高对比度清晰边框与轻盈投影；节点间使用连续流畅的 2px 玻璃质感连接线；项目下可直接添加任务或模块，任务下可再添加一层子任务；可在大纲列表与任务树间平滑切换，任务树固定在面板内滚动查看并随窗口大小自动缩放适配
- 项目、模块和任务统一使用弹窗创建/编辑；新建可执行任务必须设置大于 0 的计划用时，并支持折叠、拖拽层级、进度、优先级与截止日期；含子任务的任务作为容器管理，计时请从叶子任务开始
- 开始、暂停、恢复和结束学习计时；达到计划用时时显示站内/浏览器提醒但继续计时；项目和模块汇总末级任务的预算与实际时长
- 每日计划、长期任务引用、临时事项、完成进度与连续打卡；今日任务勾选完成状态即时同步到项目任务树（以大勾选符号显式标示）；今日页面左侧为专注计时、右侧为今日任务列表，底部并排展示月度计时日历与按小时统计的今日专注分布，窄屏自上而下依次排列并提供通透宽松的排版
- 日期范围统计、每日趋势、任务投入分布与预算偏差
- 用户搜索、伙伴邀请、接受/拒绝、解除伙伴、屏蔽与取消屏蔽
- 伙伴计划分享，可独立决定是否公开计划/实际时长
- 固定选项鼓励、持久化通知和 WebSocket 实时推送
- 计时、任务和每日计划的 IndexedDB 离线保存与联网自动重放
- PostgreSQL 行级安全策略、跨所有者约束和 Alembic 数据库迁移
- 整体界面采用现代 Apple Liquid Glass 材质与克制精致的 2.5D 空间感设计，正文、表单与图表保持稳定清晰，避免厚重繁杂视觉

软件没有自由聊天、公开动态、排行榜或需求文档之外的社交功能。

## 技术结构

```text
frontend/               Vue 3 + Vite + TypeScript + Pinia + Dexie
backend/                FastAPI + SQLAlchemy Async + Pydantic
backend/migrations/     Alembic + PostgreSQL RLS / 完整性触发器
supabase/migrations/    Supabase 首次建库与安全加固迁移
backend/tests/          SQLite API 回归测试
docs/                   架构、数据库、离线同步、API 与部署文档
compose.yaml            本地开发 PostgreSQL
compose.production.yaml 完整生产容器编排
vercel.json             Vercel Services：Vite 前端 `/` + FastAPI 后端 `/api`
```

## 快速启动

完整步骤见 [部署教程](docs/deployment.md)。

macOS / Linux 可在仓库根目录直接启动；不需要执行 `corepack enable`，也不需要管理员权限：

```bash
cd /Users/wei/Documents/praxis/git-time
corepack pnpm dev
```

该命令会安装前端缺失依赖、执行数据库迁移，并启动前端与本地后端。

仓库也支持在同一个 Vercel Project 中通过 Vercel Services 部署前后端；Vercel 配置、环境变量和上线步骤见
[Vercel Services 部署](docs/deployment.md#二vercel-services-部署)。

```powershell
# 1. 按 docs/supabase-setup.md 配置 Supabase Auth 与数据库连接
#    数据库密码可用 .\scripts\configure-supabase-database.ps1 安全录入并验证；支持特殊字符密码

# 2. 后端（新终端；也可保留 SQLite 做纯本地预览）
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

`pnpm dev` 会检查并启动完整的本地服务（数据库迁移、后端与前端），已经运行的健康服务会直接复用；终端保持运行期间会持续检查健康状态，并在本项目启动的后端意外退出时自动恢复。
Vite 开发服务器也会直接守护本地后端，因此即使使用 `pnpm dev:web`，后端未运行时也会自动完成迁移并启动，意外退出后会自动恢复。
本地预览使用 SQLite 时也会执行完整 Alembic 迁移；PostgreSQL 专用的枚举与 RLS 语句会自动跳过。

打开 `http://localhost:5174`。开发服务器启用了固定端口；如果端口已被占用，
请先关闭旧进程，不要改用其他端口，以免浏览器本地同步队列被拆分。

也可以在仓库根目录使用固定配置启动前后端；脚本会先执行数据库迁移，
并确认数据库健康后再报告启动成功：

```powershell
.\scripts\start-local.cmd
```

停止这组本地服务：

```powershell
.\scripts\stop-local.cmd
```

如果希望固定预览链接在每次登录 Windows 后自动启动并持续守护，可执行：

```powershell
.\scripts\install-preview-autostart.ps1
```

预览地址始终为 `http://localhost:5174`。完整说明及卸载方式见
[固定本地预览](docs/local-preview.md)。

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
- [Supabase MVP 配置](docs/supabase-setup.md)
- [固定本地预览](docs/local-preview.md)

## 文档维护约定

所有用户可见功能、交互流程、API、数据库或离线同步行为的修改，都必须在同一次改动中更新对应文档。
仓库根目录的 `AGENTS.md` 保存了这条长期维护规则，后续开发不能只修改代码而遗漏文档。
