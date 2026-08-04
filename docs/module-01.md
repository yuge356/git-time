# 模块 1：项目基础、账户认证与用户资料

## 本模块范围

- 创建 Vue 3 + Vite 和 FastAPI 工程骨架
- 邮箱注册和登录
- JWT Bearer 身份认证
- 查看和修改个人资料
- PostgreSQL 初始迁移
- `users`、`profiles` 的数据库级行权限策略
- 健康检查、错误状态和基础测试

本模块没有提前实现任务、计时、每日计划、伙伴或通知功能。

## 本地运行

### 1. 启动 PostgreSQL

```bash
docker compose up -d postgres
```

### 2. 启动后端

```bash
cd backend
python -m venv .venv
```

Windows PowerShell：

```powershell
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
Copy-Item .env.example .env
alembic upgrade head
uvicorn app.main:app --reload
```

API 文档地址：`http://localhost:8000/docs`

### 3. 启动前端

```bash
cd frontend
npm install
copy .env.example .env
npm run dev
```

前端地址：`http://localhost:5174`

## 验证命令

后端：

```bash
cd backend
pytest
ruff check .
```

前端：

```bash
cd frontend
npm run type-check
npm run build
```
