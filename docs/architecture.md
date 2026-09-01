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

### 数据库连接与延迟

托管数据库位于远程会话模式连接池之后：整个项目只有十几个客户端槽位，本地到库的单次往返约
100ms。后端连接池因此被刻意压得很小（`pool_size=2` + `max_overflow=2`），**每个正在处理的请求
占用一个槽位**。围绕这一点有四条约定：

- **保活 + `pool_pre_ping`**：`app.main` 的保活循环每 45 秒 ping 池内两条连接，让连接保持热
  可用，省下每次借出时的 TLS 握手；远程池会回收空闲连接，因此 `pool_pre_ping` 保持开启，避免把
  已失效的连接交给请求后以一个看不出原因的 500 结束。
- **合并串行往返**：`POST /daily-plans/open` 在一个事务里完成“取得或创建当日计划 + 按排期补齐 +
  打卡”。这三步此前是三到四个串行请求，是今日页打开慢的主要原因。
- **共享一次行加载**：`GET /analytics/dashboard` 与 `GET /analytics/today-overview` 都在**请求
  自己的那一条连接**上完成。它们各自只加载一次任务与 Session 行，再在 Python 里切出各段结果；
  早期版本额外借出第二条连接做并发，反而更快耗尽项目的槽位，让每个请求都变成 500。
- **前端限流与重试**：`services/http.ts` 中的 axios 实例最多允许 3 个请求同时在网，其余排队；
  幂等的 GET 在 500/502/503/504、超时和网络错误时最多重试 3 次（指数退避）。页面同时打开五六个
  请求正是今日页与伙伴页图表空白并弹出“服务器处理请求时出错”的原因。
- **可重试的错误语义**：连接池等待超时与断开的连接返回 503（附 `Retry-After`）而不是 500，
  客户端因此会退避重放，离线队列也会把这类失败当成网络问题保留操作，而不是当成被服务器拒绝。

前端统计视图纳入 KeepAlive，切回时立即展示缓存内容并后台刷新一次。

前端一律“先显示缓存、再后台刷新”：任务列表和当日计划在发起网络请求之前先用 IndexedDB 里的副本
渲染（本地读取约 1ms，远程往返上百毫秒），拿到服务端数据后原地替换；通知中心的两个请求推迟到
浏览器空闲后再发，不与页面自身的数据抢占有限的并发连接。

前端刷新页面的恢复路径同样按"先显示、后同步"组织：账户资料缓存于 localStorage（按用户 ID 分键，
登录与资料刷新时写入），刷新时立即复用并后台请求 `/auth/me` 更新；计时器本地有活动快照时直接恢复
显示，本地无快照且无待重放队列时只等待一次 `GET /sessions/active`，历史列表与 outbox 重放均在
后台进行。

## 2. 主要业务流

### 计时

前端先把完整 Session 快照写入 IndexedDB（并进入同步 outbox），UI 操作立即返回；随后在后台
尝试 `PUT /sessions/{id}`，失败时由离线同步按 `client_updated_at` 顺序重放。运行中时长由
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

**排期即今日任务**：`POST /daily-plans/{id}/auto-populate` 会把当天排期的叶子任务补进计划——
重复规则命中该日、`due_date` 等于该日，或该日落在任务的 `planned_start_date`~`planned_end_date`
计划窗口内。前端 `stores/daily-plans.ts` 的 `taskScheduledOnDate` 使用完全相同的规则，因此在线
补齐和离线补齐结果一致，项目页安排好的任务不会时有时无。计划项仍是当天快照：补齐只新增，删除只能
通过显式的删除接口。

### 伙伴与分享

伙伴邀请必须被接收。搜索、邀请、分享、查看和鼓励均检查双向屏蔽。分享默认只公开标题和完成状态；
只有 `share_duration=true` 才返回计划时长和实际时长。

待处理的邀请必须始终对收件人可见：`profiles` 的发现策略把 PENDING 关系与 ACCEPTED 一同放行，
而 `to_partnership_response` 在资料确实读不到时也只把伙伴降级成“未公开用户”，不会丢掉整条邀请。
伙伴页的各个面板独立加载（`Promise.allSettled`），一个请求失败不会连带清空邀请列表；
收到 `PARTNER_INVITE` / `PARTNER_ACCEPTED` 通知时页面会自动重新拉取关系列表。页面按
“待办 → 动态 → 管理”编排：待处理邀请是顶部横幅，左侧主栏是收到的分享，右侧边栏依次是分享我的
计划、我的伙伴（含查找邀请）和折叠的其他关系。

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
| 项目模板库 | project templates |
| 伙伴与屏蔽 | partnerships、blocks |
| 分享与鼓励 | plan shares、encouragements |
| 通知中心（在个人资料页内） | notifications、WebSocket |
| IndexedDB 同步 | 幂等客户端 UUID API |

Supabase 使用非对称签名密钥时，API 通过缓存的 JWKS 在本地验证访问令牌，避免每个业务请求再次访问
Auth；旧版 HS256 令牌或 JWKS 暂时不可用时仍通过 Supabase `/auth/v1/user` 安全校验。统计页使用
单一 dashboard 请求聚合范围、今日与打卡数据，今日页使用单一 today-overview 请求聚合月历、单日
专注分布与计划进度表：后端各自只做一次行加载并派生全部结果，前端先立即渲染已有数字，本地计时同步
与统计请求并行执行，同步完成后自动静默刷新一次，避免串行等待全部离线队列重放。

前端通过统一错误翻译层处理 FastAPI `detail`、Axios 网络错误、IndexedDB DOMException 和本地状态错误。
当前中文界面只展示中文提醒；翻译映射与业务异常分离，后续增加英文界面时可以复用同一错误标识和状态码。
