# 模块 1：项目基础、账户认证与用户资料

## 本模块范围

- 创建 Vue 3 + Vite 和 FastAPI 工程骨架
- Supabase Auth 邮箱或手机号 + 密码注册登录；手机号注册根据 Vercel/Cloudflare 从访问 IP 提供的国家代码预选区号，获取不到时默认 `+86`，用户可在下拉菜单中更换或手动输入其他区号
- 完整手机号仍使用 E.164 国际格式（如 `+8613800138000`），并通过内部邮箱别名登录，不启用短信、OTP 或 Supabase 原生 Phone provider
- MVP 关闭邮箱确认，不发送邮件或短信验证码；暂不提供找回密码
- 未登录用户访问 `/` 时先看到 DayFlow 欢迎页；首张轮播使用网页原生横向任务树动效，按照“叶子任务完成 → 连接线回传 → 父任务完成 → 项目根节点完成”的顺序演示时间预算和项目进度，节点始终使用圆角矩形并提供克制的液态填充、路径式对号与最终轻微光泽；后续依次展示最新的今日任务、时间统计和项目思维导图真实截图，并提供清晰的登录、注册入口，手机端使用触摸滚动与单列布局
- 登录页采用居中的紫白左右分栏圆角卡片，欢迎语、表单、按钮和错误提示全部使用中文；登录与注册在当前页面内切换，原 `/register` 地址兼容地打开注册状态，窄屏自动切换为上下布局
- 新注册账号在 Supabase `user_metadata` 中写入 `onboarding_completed=false`，首次登录进入 `/onboarding`；指引包含今日任务、项目/任务与时间统计三个步骤，可上一步、下一步、跳过或完成。完成状态通过 `updateUser` 写回元数据，不新增业务数据库字段
- 为兼容上线前已经存在的账号，缺少 `onboarding_completed` 元数据时默认视为已经完成，老用户登录后直接进入 `/today`
- 产品品牌统一为 DayFlow；Logo 使用紫色圆角底和大号白色 DF 字母，优先采用华文琥珀（STHupo）字体、Arial 回退并保持适中字母间距，不显示中文副标题
- 全局界面在不改变原有配色、布局和组件结构的前提下使用轻度玻璃视觉增强：欢迎页展示框、登录卡片、Onboarding 容器、应用侧栏、主要业务卡片和浮层使用接近实色的半透明表面、弱模糊、淡描边与柔和阴影；正文区域、表格、图表、按钮和表单保持清晰稳定，移动端进一步降低模糊与阴影
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

## 认证与首次使用验收

1. 退出登录后访问 `/`，显示欢迎页而不是应用壳层；登录和注册按钮都打开中文认证页面。
2. 新注册账号进入 `/onboarding`，刷新后仍停留在指引；完成或跳过后进入 `/today`。
3. 再次登录同一账号不重复显示指引；升级前创建、没有 onboarding 元数据的老账号也直接进入 `/today`。
4. 登录态由 Supabase JS 持久化并自动刷新，业务 API 继续使用相同的 Supabase Access Token。
5. 打开手机号注册时默认显示中国大陆 `+86`；生产环境存在可用的 IP 国家信息时自动切换，用户仍可手动修改。
