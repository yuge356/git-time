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
| 项目模板 | `GET /project-templates` | 当前用户保存的项目模板 |
| 项目模板 | `POST /project-templates` | 新建模板；重复的客户端 `id` 视为更新 |
| 项目模板 | `PATCH /project-templates/{id}` | 修改模板 |
| 项目模板 | `DELETE /project-templates/{id}` | 软删除模板 |
| 计时 | `GET /sessions` | 最近 Session |
| 计时 | `GET /sessions/active` | 当前活动 Session |
| 计时 | `PUT /sessions/{id}` | 幂等写入 Session 快照（`complete_daily_item` 决定结束计时是否同时完成任务） |
| 每日计划 | `POST /daily-plans` | 创建/幂等读取日期计划 |
| 每日计划 | `GET /daily-plans/by-date/{date}` | 日期计划 |
| 每日计划 | `POST /daily-plans/open` | 一次完成“取得或创建当日计划 + 按排期补齐 + 打卡”，今日页加载只发一个请求 |
| 每日计划 | `POST /daily-plans/{id}/auto-populate` | 按当日排期补齐计划项（重复规则、截止日期或计划窗口命中该日） |
| 每日计划 | `POST /daily-plans/{id}/items` | 添加计划项 |
| 每日计划 | `PATCH /daily-plan-items/{id}` | 修改计划项 |
| 每日计划 | `DELETE /daily-plan-items/{id}` | 删除计划项 |
| 打卡 | `GET /check-ins/{date}` | 时长、完成数、连续天数 |
| 统计 | `GET /analytics/summary` | 日期范围统计 |
| 统计 | `GET /analytics/dashboard` | 一次返回统计页范围汇总、今日汇总和打卡数据，减少页面请求与认证往返 |
| 统计 | `GET /analytics/hourly-focus?day=YYYY-MM-DD` | 单日按小时专注分布（仅选定日期，按计时开始的小时归属，使用资料时区） |
| 统计 | `GET /analytics/task-daily?date_from=&date_to=` | 每任务每日学习秒数（今日页计划进度表数据；仅返回有正时长记录的任务） |
| 统计 | `GET /analytics/today-overview` | 一次返回今日页的月历趋势、单日专注分布与计划进度表数据 |
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

任务创建和修改载荷可包含 `priority`、`due_date`、`planned_start_date`、`planned_end_date` 与
`dependency_ids`。`planned_start_date` / `planned_end_date` 仅对可执行任务（`TASK` 节点）有效，
用于今日页甘特图的计划窗口与拖拽排期；对项目 / 模块设置会返回 400，开始日期晚于结束日期也会返回
400。任务响应始终返回这些字段；`dependency_ids` 表示当前任务的前置任务列表，接口拒绝自身依赖、
跨用户依赖和循环依赖。

`GET /analytics/summary` 必须提供 `date_from=YYYY-MM-DD` 与 `date_to=YYYY-MM-DD`，范围最多
366 天。

`GET /analytics/hourly-focus` 必须提供 `day=YYYY-MM-DD`，返回 `date`、`total_seconds` 与
48 条 `slots[{ index, seconds }]`；`index` 从午夜起按半小时递增（如 index 18 表示本地 09:00–09:30），
Session 按其开始时刻的资料时区半小时槽位归属，正在计时的增量由前端实时叠加到当前槽位。

`GET /analytics/task-daily` 必须提供 `date_from=YYYY-MM-DD` 与 `date_to=YYYY-MM-DD`（最多 366 天），
返回 `tasks[{ task_id, title, total_seconds, daily[{ date, seconds }] }]`；Session 按其开始时刻的
资料时区日期归属，仅统计关联了项目任务的 Session，无正时长记录的任务不会出现。

数据库繁忙或连接被回收时，接口返回 503（附 `Retry-After`）而不是 500：连接池等待超时和被驱动作废的
连接都是暂时性问题，客户端应退避重放；数据库真正拒绝的语句仍然返回 500。

`GET /analytics/today-overview` 必须提供 `calendar_from`、`calendar_to`、`focus_day`、`gantt_from`
与 `gantt_to`（两段范围各自最多 366 天），返回
`{ calendar_trend, hourly_focus, task_daily }`，字段与 `summary.daily_trend`、`hourly-focus`、
`task-daily` 完全一致。今日页首次加载改用这一个请求：三个独立请求会同时占满后端很小的数据库连接池，
超出的请求超时后页面就会在空白图表上显示服务器错误提示。切换月份或查看历史某天时仍使用单独的接口。

`POST /daily-plans/open` 接受 `{ plan_date, id? }`，返回 `{ plan, check_in }`：日期计划不存在时按需
创建（并发创建同一天时复用已存在的行），随后执行排期补齐并计算打卡数据，全部在同一个事务里完成。
今日页此前需要“读取 →（404 时）创建 → 补齐 → 打卡”三到四个串行请求，每个都要一次远程数据库往返。

`POST /daily-plans/{id}/auto-populate` 会把当日排期的可执行任务补进该日计划：命中重复规则、
`due_date` 等于该日期，或该日期落在 `planned_start_date`~`planned_end_date` 之间的任务都会被加入。
已完成的任务和含有子任务的容器任务不会被加入；计划项是当日快照，补齐操作只新增、不删除已有条目。
一项任务在一天里只占一条计划项：补齐（以及 `open`）开始前会先合并同一任务的重复条目，保留有计时
记录或已完成的那条，另一条被软删除；两条都有计时记录时都会保留，已记录的时长不会被丢弃。

`POST /daily-plans/{id}/items` 对同一任务是幂等的：该日计划里已有引用同一 `task_id` 的条目时直接返回
已有条目，而不是新建第二条。浏览器导入新排期的任务与服务端排期补齐可能同时发生，两者各自生成条目
id，此前会让同一个任务在“今日任务”里出现两次。

项目模板载荷为 `{ name, description, icon, preset_key, budget_mode, fixed_budget_seconds,
default_estimated_seconds, default_repeat_rule, structure }`。`structure` 是嵌套的
`[{ node_type: MODULE|TASK, title, estimated_seconds, children }]` 大纲，只描述蓝图、不创建任务行：
模块只能位于项目下、最多三层嵌套、最多 200 个节点，节点类型不能是 `PROJECT`，违反时返回 422。
创建项目时由前端按大纲逐级调用 `POST /tasks`，因此套用模板同样走离线队列。

`PUT /sessions/{id}` 的 `complete_daily_item` 默认为 `true`。写入 `COMPLETED` 且该值为 `false` 时，
计划项不会被标记完成，只从“进行中”回到“已暂停”：结束计时不等于完成任务，之后还能再次开始并继续累计。
计划项的 `actual_seconds` 始终是该条目全部 Session 时长之和，只统计在本软件中实际计时的时间，直接
标记完成不会补记任何时长。

Supabase Auth 的客户端调用为 `signUp({ email, password, options.data })`、`signInWithPassword(...)`、
`updateUser({ data })` 和 `signOut()`；注册元数据中的 `onboarding_completed=false` 标记新账号需要首次使用
指引，完成或跳过时更新为 `true`。该标记不参与 FastAPI 权限判断或 PostgreSQL RLS。
邮箱账号直接使用邮箱，手机号账号使用确定性的 `phone.<digits>@phone.dayflow.invalid` 内部别名，因此不需要
Supabase Phone provider 或短信供应商。DayFlow 不代理或记录明文密码；`GET /auth/me` 会校验 Supabase
令牌、隐藏内部别名并返回真实业务资料。
