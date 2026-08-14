# 模块 1：项目基础、账户认证与用户资料

## 本模块范围

- 创建 Vue 3 + Vite 和 FastAPI 工程骨架
- Supabase Auth 邮箱或手机号 + 密码注册登录；手机号必须使用 E.164 国际格式（如 `+8613800138000`），
  并通过内部邮箱别名登录，不启用短信、OTP 或 Supabase 原生 Phone provider
- MVP 关闭邮箱确认，不发送邮件或短信验证码；暂不提供找回密码
- 登录页采用居中的紫白左右分栏圆角卡片：左侧显示英文欢迎语，右侧提供登录或注册表单；点击 Register / Login 只在当前卡片内切换表单，不跳转页面，原 `/register` 地址会兼容地打开同一页面的注册状态；窄屏自动切换为上下布局
- 产品品牌统一为 DayFlow；Logo 使用紫色圆角底和大号白色 DF 字母，优先采用华文琥珀（STHupo）字体、Arial 回退并保持适中字母间距，不显示中文副标题
- Supabase 自动持久化和刷新会话；FastAPI 校验 Supabase Bearer Token
- 查看和修改个人资料
- Supabase 托管 PostgreSQL 初始迁移与账号资料镜像触发器
- `users`、`profiles` 的数据库级行权限策略
- 健康检查、错误状态和基础测试

本模块没有提前实现任务、计时、每日计划、伙伴或通知功能。

详细的后台开关、连接字符串和环境变量步骤见 [Supabase MVP 配置](supabase-setup.md)。

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
