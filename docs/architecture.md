# 整体架构

## 1. 分层

```text
浏览器
├─ Vue 页面与组件
├─ Pinia 业务状态
├─ Supabase JS：注册、登录、会话刷新、首次指引状态
├─ Axios HTTP / WebSocket：携带 Supabase Access Token
└─ Dexie IndexedDB
   ├─ 计时快照与 Session 待同步队列
   ├─ 任务、每日计划缓存
   └─ 任务/计划有序操作队列
          │
          ▼
FastAPI
├─ 向 Supabase Auth /auth/v1/user 校验 Access Token
├─ API 路由：任务、计时、计划、统计、伙伴、分享、通知
├─ Pydantic：请求验证与响应边界
├─ Service：所有权、状态机、预算、聚合、分享权限
└─ SQLAlchemy Async：事务和数据访问
          │
          ▼
Supabase 托管 PostgreSQL
├─ 表、外键、检查约束、唯一索引
├─ Alembic 版本迁移
├─ 所有者一致性触发器
└─ Row Level Security
```

## 2. 主要业务流

### 计时

前端先把完整 Session 快照写入 IndexedDB，再尝试 `PUT /sessions/{id}`。运行中时长由
`duration_seconds + 当前时间 - last_resumed_at` 计算，不依赖浏览器每秒累加。旧的离线快照由
`client_updated_at` 判定并忽略。

### 任务预算

任务树固定为“项目 / 课程 → 模块 → 可执行任务”。只有末级任务可以关联 Session；项目和模块的
完成度、预算与实际时长由服务端统一汇总。容器预算可以自动汇总末级任务，也可以使用固定上限，
预算状态按 80%、100%、150% 三个阈值计算。

任务数据在 API、Pinia 和 IndexedDB 中保持为独立的平铺记录，`parent_id` 表示层级，依赖关系保存为
独立有向边。项目页面只负责把同一份数据渲染成“任务树”或“大纲列表”视图，因此以后增加看板、日历、
甘特图时不需要改变底层任务模型。用户的视图选择保存在浏览器本地；新增和编辑统一通过模态弹窗完成。

### 每日计划

每位用户每天最多一份计划。计划项可以引用长期任务，也可以只在当天存在。Session 可关联计划项；
关联长期任务的计划项同时保留 `task_id`，因此每日进度和长期预算使用同一份计时数据。

### 伙伴与分享

伙伴邀请必须被接收。搜索、邀请、分享、查看和鼓励均检查双向屏蔽。分享默认只公开标题和完成状态；
只有 `share_duration=true` 才返回计划时长和实际时长。

### 通知

通知先写入数据库，再通过 WebSocket 尝试推送。浏览器断线后重新读取持久化通知，因此实时连接不是
可靠性的唯一来源。

### 公开入口与首次使用

未登录访问 `/` 时由 Vue Router 显示公开欢迎页，受保护业务路由仍会跳转到中文登录页。注册时前端在
Supabase Auth `user_metadata` 中写入 `onboarding_completed=false`；路由守卫据此把新账号导向
`/onboarding`。完成或跳过指引时调用 Supabase `updateUser` 写入 `onboarding_completed=true` 和完成时间。

该字段只控制非安全性质的界面流程，不参与 API 授权或 RLS 判断。升级前已经存在且缺少该字段的账号默认
视为已完成，因此不会被错误拦截；业务 `profiles` 表和 PostgreSQL schema 均无需修改。

## 3. 安全边界

- Supabase Auth 单独保存密码并签发/刷新访问令牌；DayFlow 数据表不保存 Supabase 密码或密码哈希。
- 首次使用状态保存在可由当前用户更新的 Auth `user_metadata`，只用于前端导航，不能作为权限依据。
- Supabase 托管项目启用原生 Phone provider 会强制要求短信供应商。MVP 不接入短信，因此前端把已校验的 E.164
  手机号确定性映射为 `phone.<digits>@phone.dayflow.invalid` 内部邮箱身份；FastAPI 和数据库触发器再还原手机号，
  且不会把内部别名暴露到业务 API。
- 前端只持有公开的 publishable key，不得放置 service role key、数据库密码或 JWT 私钥。
- FastAPI 用公开 key 调用 Supabase Auth 用户接口校验令牌，兼容项目当前及以后更换的 JWT 签名方式。
- 浏览器不持有数据库凭据。
- 每次认证请求设置事务级 `app.current_user_id`。
- FastAPI 的池连接建立后执行 `SET ROLE dayflow_app`；该角色无登录、无 `BYPASSRLS`，数据库密码对应的
  管理员身份不会进入业务查询。`postgres` 仅获得进入该角色所需的 `SET TRUE` 成员选项，保持
  `INHERIT FALSE`，因此连接建立前不会自动继承业务权限。Alembic 使用独立连接，仍可执行迁移。
- PostgreSQL RLS 限制账户、任务、Session、计划、伙伴、分享、鼓励和通知可见范围。
- API 服务层重复检查所有权、伙伴状态和屏蔽状态，形成应用层与数据库层双重约束。
- CORS 来源、Supabase 公共配置和数据库连接均从环境变量读取。

`APP_AUTH_PROVIDER=local` 仅用于离线开发和自动化测试，保留旧的 FastAPI 邮箱注册接口；MVP 实际运行使用
`APP_AUTH_PROVIDER=supabase`。Supabase 账户首次访问 API 时由数据库触发器（同库）或 API 兼容桥（本地库）
建立 `public.users` 与 `profiles` 镜像。WebSocket 与普通 HTTP 请求共用同一令牌校验流程。

## 4. 前后端模块

| 前端 | 后端 |
|---|---|
| 欢迎页、登录、注册、首次指引、资料 | auth、profiles |
| 任务树/大纲列表任务视图、弹窗编辑、预算提示 | tasks、task service |
| 计时器、历史、离线队列 | sessions、session state machine |
| 今日计划、打卡 | daily plans、check-ins |
| 统计图表 | analytics |

Supabase 使用非对称签名密钥时，API 通过缓存的 JWKS 在本地验证访问令牌，避免每个业务请求再次访问 Auth；旧版 HS256 令牌或 JWKS 暂时不可用时仍通过 Supabase `/auth/v1/user` 安全校验。统计页使用单一 dashboard 请求聚合范围、今日与打卡数据：后端只做一次行加载并同时派生范围汇总与今日汇总，前端先立即渲染已有数字，本地计时同步与统计请求并行执行，同步完成后自动静默刷新一次，避免串行等待全部离线队列重放。
| 伙伴与屏蔽 | partnerships、blocks |
| 分享与鼓励 | plan shares、encouragements |
| 通知中心 | notifications、WebSocket |
| IndexedDB 同步 | 幂等客户端 UUID API |

前端通过统一错误翻译层处理 FastAPI `detail`、Axios 网络错误、IndexedDB DOMException 和本地状态错误。
当前中文界面只展示中文提醒；翻译映射与业务异常分离，后续增加英文界面时可以复用同一错误标识和状态码。
