# Supabase MVP 配置

DayFlow 的 MVP 使用一个 Supabase 免费项目完成两件事：

1. Supabase Auth 管理邮箱/手机号 + 密码账号和登录会话；
2. Supabase Postgres 保存用户资料、项目、任务、今日计划、计时记录以及统计所需的源数据。

统计数据不重复保存为容易失真的汇总表。时间统计接口直接聚合 `sessions`、`tasks`、
`daily_plans` 和 `daily_plan_items`，所以完成计时后写入一次即可在统计页同步体现。

## 当前项目已经完成的工作

- 已连接现有免费 Supabase 项目，没有新建收费项目。
- 已部署 `supabase/migrations/20260814000100_dayflow_mvp.sql` 完整业务结构。
- 已部署函数权限、RLS 与索引安全加固迁移。
- Supabase 数据库安全顾问当前为 0 条安全告警。
- 前端已经配置 Supabase JS，后端已经支持校验 Supabase Access Token。
- 邮箱和手机号共用同一个登录输入框；手机号要求 E.164 格式，例如 `+8613800138000`。

## 还需要在 Supabase 控制台完成的设置

这些是 Supabase Auth 的项目级开关，代码和数据库迁移不能代替控制台配置。

### 1. 关闭验证邮件并保持短信服务关闭

进入 Supabase 项目后：

1. 打开 **Authentication → Providers → Email**；
2. 保持 Email 登录开启，关闭 **Confirm email**；
3. 保持 **Phone provider 关闭**，不要配置 Twilio 或其他短信服务商；
4. DayFlow 会把 E.164 手机号映射为 Supabase Email Auth 的内部别名，用户界面仍然只显示和输入手机号；
5. 在 **Authentication → URL Configuration** 把本地 Site URL 设置为
   `http://localhost:5174`。

如果以后正式上线，Site URL 和 Redirect URLs 要换成正式 HTTPS 域名。手机号未经过所有权验证，也无法通过
短信找回密码；这适合当前 MVP，但公开发布前应重新评估滥用注册、号码回收和账户恢复风险。

### 2. 填入数据库 Session pooler 连接

FastAPI 是长期运行服务，免费项目本地开发优先使用 Supabase **Session pooler**：

当前项目已确认使用新加坡区域的 Session pooler。推荐在仓库根目录执行安全配置脚本：

```powershell
.\scripts\configure-supabase-database.ps1
```

脚本会以隐藏输入方式读取数据库密码，自动进行 URL 编码，先验证连接，再写入被 Git 忽略的
`backend/.env`。密码不会出现在命令历史或终端输出中；验证失败时不会覆盖原连接配置。密码含
`@`、`%`、`#` 等特殊字符时也可直接使用，迁移配置会在内部完成 Alembic `ConfigParser`
所需的百分号转义，不需要用户修改密码或手工处理连接串。

手动配置时也可以按下面步骤操作：

1. 点击项目顶部 **Connect**；
2. 选择 **Session pooler**，复制 URI；
3. 如果忘记数据库密码，在 **Project Settings → Database** 重置一次；
4. 把 URI 的 `postgresql://` 改成 `postgresql+asyncpg://`；
5. 如果密码含 `@`、`:`、`/`、`#` 等字符，先进行 URL 编码；
6. 写入 `backend/.env` 的 `APP_DATABASE_URL`，不要写入前端文件或提交 Git。

PowerShell 可生成编码后的密码：

```powershell
[uri]::EscapeDataString('在这里输入数据库密码')
```

连接格式以控制台复制结果为准，通常类似：

```text
postgresql+asyncpg://postgres.PROJECT_REF:URL_ENCODED_PASSWORD@POOLER_HOST:5432/postgres
```

## 环境变量

后端 `backend/.env`：

```dotenv
APP_AUTH_PROVIDER=supabase
APP_SUPABASE_URL=https://PROJECT_REF.supabase.co
APP_SUPABASE_PUBLISHABLE_KEY=sb_publishable_xxx
APP_DATABASE_URL=postgresql+asyncpg://postgres.PROJECT_REF:URL_ENCODED_PASSWORD@POOLER_HOST:5432/postgres
APP_DATABASE_ROLE=dayflow_app
```

前端 `frontend/.env`：

```dotenv
VITE_API_BASE_URL=/api/v1
VITE_SUPABASE_URL=https://PROJECT_REF.supabase.co
VITE_SUPABASE_PUBLISHABLE_KEY=sb_publishable_xxx
```

Publishable key 本来就用于浏览器，可以出现在前端构建中；数据库密码、service role key 和 JWT 私钥绝不能
写入 `VITE_` 变量。

数据库 URI 使用项目管理员账号只是为了让 Alembic 能运行迁移。FastAPI 连接池建立后会自动执行
`SET ROLE dayflow_app`，日常业务查询因此使用无管理员权限且强制执行 RLS 的运行角色。
Supabase 的 PostgreSQL 16+ 角色成员关系会单独记录 `SET` 选项；迁移会为 `postgres` 明确设置
`SET TRUE`，同时保留 `INHERIT FALSE`，让连接可以主动进入运行角色但不会默认继承其权限。
该角色只获得现有 12 张业务表的增删改查权限和两个 RLS 身份函数的执行权限；没有默认未来对象权限，新增表
时必须在对应迁移中显式授权。

## 验证顺序

1. 重启前后端，使 `.env` 生效；
2. 在登录页先创建一个邮箱账号，应立即登录且不收到确认邮件；
3. 退出后用邮箱和密码重新登录；
4. 再创建一个 E.164 手机号账号，应立即登录且不触发短信；Supabase `auth.users` 中会使用内部邮箱别名，
   DayFlow `users.phone` 中应保存原始 E.164 手机号；
5. 新建项目、任务并完成一次计时；
6. 在时间统计页确认投入时长和完成项更新；
7. 在 Supabase **Table Editor** 检查 `profiles`、`tasks`、`sessions` 是否出现对应记录。

本地自动化测试仍将 `APP_AUTH_PROVIDER` 临时切换为 `local` 并使用内存 SQLite，因此不会向免费项目写入
测试账号或测试任务。
