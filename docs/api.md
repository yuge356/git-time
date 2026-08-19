# API 清单

所有地址以 `/api/v1` 为前缀；MVP 的注册、登录和令牌刷新由 Supabase Auth 提供，前端访问 DayFlow API 时使用
`Authorization: Bearer <supabase_access_token>`。WebSocket 在查询参数中携带同一令牌并执行相同校验。

| 模块 | 方法与地址 | 用途 |
|---|---|---|
| 兼容认证 | `POST /auth/register` | 仅 `APP_AUTH_PROVIDER=local` 的测试/离线开发注册 |
| 注册便捷设置 | `GET /auth/registration-country` | 从托管代理的 IP 国家请求头返回两位国家代码，不可用于鉴权；缺省为 `CN` |
| 兼容认证 | `POST /auth/login` | 仅 `APP_AUTH_PROVIDER=local` 的测试/离线开发登录 |
| 认证 | `GET /auth/me` | 当前账户 |
| 资料 | `GET /profiles/me` | 当前资料 |
| 资料 | `PATCH /profiles/me` | 修改资料、时区与可搜索性 |
| 任务 | `GET /tasks` | 任务平铺列表及预算统计 |
| 任务 | `POST /tasks` | 创建项目、模块或可执行任务 |
| 任务 | `GET /tasks/{id}` | 任务详情 |
| 任务 | `PATCH /tasks/{id}` | 修改任务；计划用时变更同步到今天及未来的关联每日计划条目 |
| 任务 | `POST /tasks/{id}/apply-defaults` | 把项目/模块默认值应用到已有任务 |
| 任务 | `DELETE /tasks/{id}` | 软删除任务子树 |
| 计时 | `GET /sessions` | 最近 Session |
| 计时 | `GET /sessions/active` | 当前活动 Session |
| 计时 | `PUT /sessions/{id}` | 幂等写入 Session 快照 |
| 每日计划 | `POST /daily-plans` | 创建/幂等读取日期计划 |
| 每日计划 | `GET /daily-plans/by-date/{date}` | 日期计划 |
| 每日计划 | `POST /daily-plans/{id}/items` | 添加计划项 |
| 每日计划 | `PATCH /daily-plan-items/{id}` | 修改计划项 |
| 每日计划 | `DELETE /daily-plan-items/{id}` | 删除计划项 |
| 打卡 | `GET /check-ins/{date}` | 时长、完成数、连续天数 |
| 统计 | `GET /analytics/summary` | 日期范围统计 |
| 统计 | `GET /analytics/dashboard` | 一次返回统计页范围汇总、今日汇总和打卡数据，减少页面请求与认证往返 |
| 搜索 | `GET /users/search?q=` | 搜索可发现用户 |
| 伙伴 | `GET /partnerships` | 邀请和伙伴列表 |
| 伙伴 | `POST /partnerships/invitations` | 发出邀请 |
| 伙伴 | `PATCH /partnerships/{id}` | 接受/拒绝 |
| 伙伴 | `DELETE /partnerships/{id}` | 取消或解除 |
| 屏蔽 | `GET /blocks` | 已屏蔽列表 |
| 屏蔽 | `POST /blocks/{user_id}` | 屏蔽用户 |
| 屏蔽 | `DELETE /blocks/{id}` | 取消屏蔽 |
| 分享 | `POST /plan-shares` | 分享计划 |
| 分享 | `GET /plan-shares/sent` | 已发出分享 |
| 分享 | `DELETE /plan-shares/{id}` | 撤销分享 |
| 分享 | `GET /shared-plans` | 收到的计划 |
| 鼓励 | `POST /plan-shares/{id}/encouragements` | 发送固定鼓励 |
| 通知 | `GET /notifications` | 通知列表 |
| 通知 | `GET /notifications/unread-count` | 未读数 |
| 通知 | `PATCH /notifications/{id}/read` | 标记已读 |
| 实时通知 | `WS /ws/notifications?token=` | WebSocket 推送 |

任务创建和修改载荷可包含 `priority`、`due_date` 与 `dependency_ids`。任务响应始终返回这些字段；
`dependency_ids` 表示当前任务的前置任务列表，接口拒绝自身依赖、跨用户依赖和循环依赖。

`GET /analytics/summary` 必须提供 `date_from=YYYY-MM-DD` 与 `date_to=YYYY-MM-DD`，范围最多
366 天。

Supabase Auth 的客户端调用为 `signUp({ email, password, options.data })`、`signInWithPassword(...)`、
`updateUser({ data })` 和 `signOut()`；注册元数据中的 `onboarding_completed=false` 标记新账号需要首次使用
指引，完成或跳过时更新为 `true`。该标记不参与 FastAPI 权限判断或 PostgreSQL RLS。
邮箱账号直接使用邮箱，手机号账号使用确定性的 `phone.<digits>@phone.dayflow.invalid` 内部别名，因此不需要
Supabase Phone provider 或短信供应商。DayFlow 不代理或记录明文密码；`GET /auth/me` 会校验 Supabase
令牌、隐藏内部别名并返回真实业务资料。
