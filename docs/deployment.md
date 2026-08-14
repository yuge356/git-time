# 完整部署教程

## 一、Supabase MVP 部署（推荐）

### 1. 环境要求

- Windows：Docker Desktop 4.x，并启用 Docker Compose
- Linux：Docker Engine 26+ 与 Docker Compose v2
- 一个 Supabase 免费项目
- 至少 1 GB 可用内存（数据库由 Supabase 托管）
- 服务器部署时准备域名和 HTTPS 反向代理

### 2. 创建环境文件

在项目根目录执行：

```powershell
Copy-Item .env.production.example .env.production
```

编辑 `.env.production`：

- 按 [Supabase MVP 配置](supabase-setup.md) 完成 Auth 开关和 Session pooler 连接。
- `APP_DATABASE_URL` 使用 Supabase Session pooler URI，并把密码进行 URL 编码。
- `APP_SECRET_KEY` 至少 32 个随机字符，生产环境建议 64 字符。
- `APP_CORS_ORIGINS` 改为实际访问来源，例如 `["https://learn.example.com"]`。
- 后端配置 `APP_AUTH_PROVIDER=supabase`、`APP_SUPABASE_URL` 和 publishable key。
- 前端配置同一项目的 `VITE_SUPABASE_URL` 和 publishable key。
- `HTTP_PORT` 是主机暴露端口，默认 `8080`。

PowerShell 生成随机密钥：

```powershell
[Convert]::ToHexString([Security.Cryptography.RandomNumberGenerator]::GetBytes(32))
```

### 3. 构建并启动

```powershell
docker compose --env-file .env.production -f compose.production.yaml up -d --build
```

启动顺序为后端连接 Supabase 并执行尚未执行的 Alembic 迁移，然后前端 Nginx 启动。本编排不会再创建
本地 PostgreSQL 容器。

### 4. 验证

```powershell
docker compose --env-file .env.production -f compose.production.yaml ps
Invoke-RestMethod http://localhost:8080/health
```

健康接口应返回：

```json
{"status":"ok"}
```

浏览器打开 `http://localhost:8080`，注册账户后即可使用。

### 5. 日志与停止

```powershell
docker compose --env-file .env.production -f compose.production.yaml logs -f backend
docker compose --env-file .env.production -f compose.production.yaml stop
```

停止容器不会删除 Supabase 中的数据。

### 6. 更新版本

先备份数据库，再替换代码并执行：

```powershell
docker compose --env-file .env.production -f compose.production.yaml up -d --build
```

后端启动时自动应用尚未执行的 Alembic 迁移。

### 7. 数据库备份与恢复

MVP 使用 Supabase 控制台提供的数据库备份/导出能力。手工运行 `pg_dump` 时使用控制台 **Connect** 中的
连接参数，不要把密码写入仓库。恢复前先在独立项目验证迁移和备份，避免覆盖生产数据。

### 8. 域名与 HTTPS

生产环境应让外层 Caddy、Nginx 或云负载均衡器终止 TLS，并把 HTTP 与 WebSocket 一并转发到
`127.0.0.1:8080`。WebSocket 地址位于 `/api/v1/ws/notifications`，反向代理必须保留
`Upgrade` 与 `Connection` 请求头。随后把 `APP_CORS_ORIGINS` 设置为 HTTPS 域名并重新创建后端容器。

当前实时通知管理器在单个后端进程内工作，因此生产编排固定为一个 Uvicorn worker。通知已经持久化，
短暂断线不会丢失；如果未来水平扩容，需要引入跨进程发布订阅后再增加副本。

## 二、本地开发安装

### 1. 安装软件

- Python 3.12
- Node.js 20.19+ 或 22 LTS
- pnpm 11（可由 Corepack 管理）
- PostgreSQL 17，或使用项目 `compose.yaml`

### 2. 选择本地数据库模式

日常 MVP 联调使用 Supabase Session pooler，并按 `docs/supabase-setup.md` 设置 `APP_DATABASE_URL`。
只做离线界面预览或自动化测试时，可以继续使用 SQLite；`APP_AUTH_PROVIDER=local` 只用于兼容测试，不代表
正式账号系统。

### 3. 安装并启动后端

```powershell
cd backend
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e ".[dev]"
Copy-Item .env.example .env
alembic upgrade head
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

接口文档：`http://127.0.0.1:8000/docs`  
健康检查：`http://127.0.0.1:8000/health`

如果 PowerShell 禁止激活脚本，可以不激活，直接使用：

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

### 4. 安装并启动前端

新开终端：

```powershell
cd frontend
corepack enable
pnpm install --frozen-lockfile
Copy-Item .env.example .env
pnpm dev
```

打开 `http://localhost:5174`。本地开发端口是固定的；若端口被占用，请先关闭旧进程，
不要让 Vite 自动切换端口，否则登录信息与 IndexedDB 待同步队列会被浏览器按来源隔离。

### 5. 运行测试

后端：

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\ruff.exe check app tests migrations
```

前端：

```powershell
cd frontend
pnpm run type-check
pnpm run build
```

### 6. 常见问题

- 后端提示连接数据库失败：确认 Supabase 项目为可用状态，且 `backend/.env` 使用正确的 Session pooler 地址。
- Supabase 报密码或连接错误：重新复制 Session pooler URI，并确认密码已 URL 编码。
- 手机号无法注册：保持 Phone provider 关闭，确认 Email provider 已开启、Confirm email 已关闭，并使用
  `+86...` 的 E.164 格式；DayFlow 会把手机号映射为内部邮箱身份。
- 注册后提示仍需确认：关闭 Supabase 的 Confirm email 后重新创建测试账号。
- 前端无法请求 API：确认 `frontend/.env` 为 `VITE_API_BASE_URL=/api/v1`，开发环境由
  Vite 把 `/api` 转发到 `127.0.0.1:8000`，容器环境由 Nginx 转发。
- WebSocket 无通知：确认反向代理支持 Upgrade，并检查 `APP_CORS_ORIGINS` 是否包含页面来源。
- 离线数据未立即出现在其他设备：恢复网络后保持页面打开，待“等待同步”数量归零。
