# 完整部署教程

## 一、生产容器部署（推荐）

### 1. 环境要求

- Windows：Docker Desktop 4.x，并启用 Docker Compose
- Linux：Docker Engine 26+ 与 Docker Compose v2
- 至少 2 GB 可用内存
- 服务器部署时准备域名和 HTTPS 反向代理

### 2. 创建环境文件

在项目根目录执行：

```powershell
Copy-Item .env.production.example .env.production
```

编辑 `.env.production`：

- `POSTGRES_PASSWORD` 使用长的 URL 安全密码。
- `APP_DATABASE_URL` 中的密码必须与 `POSTGRES_PASSWORD` 相同。
- `APP_SECRET_KEY` 至少 32 个随机字符，生产环境建议 64 字符。
- `APP_CORS_ORIGINS` 改为实际访问来源，例如 `["https://learn.example.com"]`。
- `HTTP_PORT` 是主机暴露端口，默认 `8080`。

PowerShell 生成随机密钥：

```powershell
[Convert]::ToHexString([Security.Cryptography.RandomNumberGenerator]::GetBytes(32))
```

### 3. 构建并启动

```powershell
docker compose --env-file .env.production -f compose.production.yaml up -d --build
```

启动顺序为 PostgreSQL 健康检查、后端自动执行 `alembic upgrade head`、前端 Nginx 启动。

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

停止不会删除数据库卷。只有明确执行 `down -v` 才会删除数据卷，不建议在生产环境使用。

### 6. 更新版本

先备份数据库，再替换代码并执行：

```powershell
docker compose --env-file .env.production -f compose.production.yaml up -d --build
```

后端启动时自动应用尚未执行的 Alembic 迁移。

### 7. 数据库备份与恢复

备份：

```powershell
docker compose --env-file .env.production -f compose.production.yaml exec -T postgres pg_dump -U time_budget_app -d time_budget_tracker -Fc > time_budget_tracker.dump
```

恢复到空数据库：

```powershell
Get-Content -AsByteStream time_budget_tracker.dump | docker compose --env-file .env.production -f compose.production.yaml exec -T postgres pg_restore -U time_budget_app -d time_budget_tracker --clean --if-exists
```

如果修改了 `POSTGRES_USER` 或 `POSTGRES_DB`，同步替换命令中的值。

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

### 2. 启动 PostgreSQL

```powershell
docker compose up -d postgres
docker compose ps
```

开发数据库：

```text
数据库：time_budget_tracker
用户：time_budget_app
端口：5432
```

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

打开 `http://localhost:5173`。

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

- 后端提示连接数据库失败：确认 PostgreSQL 容器健康，且 `backend/.env` 的连接地址正确。
- Alembic 报密码错误：开发 `compose.yaml` 与 `backend/.env.example` 密码必须一致。
- 前端无法请求 API：确认 `frontend/.env` 为 `VITE_API_BASE_URL=/api/v1`，开发环境由
  Vite 把 `/api` 转发到 `127.0.0.1:8000`，容器环境由 Nginx 转发。
- WebSocket 无通知：确认反向代理支持 Upgrade，并检查 `APP_CORS_ORIGINS` 是否包含页面来源。
- 离线数据未立即出现在其他设备：恢复网络后保持页面打开，待“等待同步”数量归零。
