# API 清单

所有地址以 `/api/v1` 为前缀；除注册、登录和 WebSocket 握手外均使用
`Authorization: Bearer <token>`。

| 模块 | 方法与地址 | 用途 |
|---|---|---|
| 认证 | `POST /auth/register` | 注册 |
| 认证 | `POST /auth/login` | 登录 |
| 认证 | `GET /auth/me` | 当前账户 |
| 资料 | `GET /profiles/me` | 当前资料 |
| 资料 | `PATCH /profiles/me` | 修改资料、时区与可搜索性 |
| 任务 | `GET /tasks` | 任务平铺列表及预算统计 |
| 任务 | `POST /tasks` | 创建任务 |
| 任务 | `GET /tasks/{id}` | 任务详情 |
| 任务 | `PATCH /tasks/{id}` | 修改任务 |
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

`GET /analytics/summary` 必须提供 `date_from=YYYY-MM-DD` 与 `date_to=YYYY-MM-DD`，范围最多
366 天。
