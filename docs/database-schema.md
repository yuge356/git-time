# 数据库表结构

数据库为 PostgreSQL 17。主键均使用 UUID，时间字段均为 `TIMESTAMPTZ`，除特别说明外不可为空。

## 枚举

| 枚举 | 值 |
|---|---|
| `task_status` | `TODO`、`IN_PROGRESS`、`PAUSED`、`DONE` |
| `session_status` | `RUNNING`、`PAUSED`、`COMPLETED` |
| `daily_plan_item_status` | `TODO`、`IN_PROGRESS`、`PAUSED`、`DONE` |
| `partnership_status` | `PENDING`、`ACCEPTED`、`DECLINED` |
| `encouragement_type` | `KEEP_GOING`、`GREAT_JOB`、`WELL_DONE`、`YOU_CAN_DO_IT` |
| `notification_type` | `PARTNER_INVITE`、`PARTNER_ACCEPTED`、`PLAN_SHARED`、`ENCOURAGEMENT`、`TASK_COMPLETED` |

## `users`

| 字段 | 类型 | 约束/说明 |
|---|---|---|
| `id` | UUID | PK |
| `email` | CITEXT | UNIQUE，登录邮箱 |
| `password_hash` | VARCHAR(255) | Argon2 哈希 |
| `is_active` | BOOLEAN | 默认 true |
| `created_at` | TIMESTAMPTZ | 创建时间 |
| `updated_at` | TIMESTAMPTZ | 更新时间 |

## `profiles`

| 字段 | 类型 | 约束/说明 |
|---|---|---|
| `id` | UUID | PK、FK → `users.id`，级联删除 |
| `username` | CITEXT | UNIQUE |
| `display_name` | VARCHAR(80) | 显示名称 |
| `avatar_url` | TEXT | 可空 |
| `bio` | VARCHAR(300) | 可空 |
| `timezone` | VARCHAR(64) | 默认 `Asia/Shanghai` |
| `is_searchable` | BOOLEAN | 是否允许被搜索 |
| `created_at` | TIMESTAMPTZ | 创建时间 |
| `updated_at` | TIMESTAMPTZ | 更新时间 |

## `tasks`

| 字段 | 类型 | 约束/说明 |
|---|---|---|
| `id` | UUID | PK |
| `owner_id` | UUID | FK → `users.id`，级联删除 |
| `parent_id` | UUID | 可空；与 `owner_id` 组成同所有者自引用 FK |
| `title` | VARCHAR(200) | 任务标题 |
| `status` | `task_status` | 默认 `TODO` |
| `estimated_seconds` | INTEGER | ≥ 0 |
| `sort_order` | INTEGER | 同级排序 |
| `completed_at` | TIMESTAMPTZ | 可空 |
| `deleted_at` | TIMESTAMPTZ | 可空；软删除 |
| `created_at` | TIMESTAMPTZ | 创建时间 |
| `updated_at` | TIMESTAMPTZ | 更新时间 |

任务触发器阻止层级循环；`(id, owner_id)` 唯一约束保证父子任务属于同一用户。

## `sessions`

| 字段 | 类型 | 约束/说明 |
|---|---|---|
| `id` | UUID | PK；由客户端生成以支持幂等重放 |
| `owner_id` | UUID | FK → `users.id` |
| `task_id` | UUID | 可空，FK → `tasks.id`，删除后置空 |
| `daily_plan_item_id` | UUID | 可空，FK → `daily_plan_items.id`，删除后置空 |
| `status` | `session_status` | 计时状态 |
| `started_at` | TIMESTAMPTZ | 开始时间 |
| `ended_at` | TIMESTAMPTZ | 完成时必填 |
| `duration_seconds` | INTEGER | 已累计的完整区间，≥ 0 |
| `last_resumed_at` | TIMESTAMPTZ | 运行中必填 |
| `client_id` | UUID | 浏览器客户端 ID |
| `client_updated_at` | TIMESTAMPTZ | 离线冲突排序时间 |
| `deleted_at` | TIMESTAMPTZ | 可空 |
| `created_at` | TIMESTAMPTZ | 创建时间 |
| `updated_at` | TIMESTAMPTZ | 更新时间 |

`task_id` 与 `daily_plan_item_id` 至少一个非空。每位用户仅允许一个未删除的
`RUNNING`/`PAUSED` Session。

## `daily_plans`

| 字段 | 类型 | 约束/说明 |
|---|---|---|
| `id` | UUID | PK |
| `owner_id` | UUID | FK → `users.id` |
| `plan_date` | DATE | 与 `owner_id` 组合唯一 |
| `deleted_at` | TIMESTAMPTZ | 可空 |
| `created_at` | TIMESTAMPTZ | 创建时间 |
| `updated_at` | TIMESTAMPTZ | 更新时间 |

## `daily_plan_items`

| 字段 | 类型 | 约束/说明 |
|---|---|---|
| `id` | UUID | PK |
| `daily_plan_id` | UUID | FK → `daily_plans.id` |
| `owner_id` | UUID | FK → `users.id`；与计划组成同所有者复合 FK |
| `task_id` | UUID | 可空，FK → `tasks.id`；空值表示临时事项 |
| `title` | VARCHAR(200) | 标题快照 |
| `status` | `daily_plan_item_status` | 默认 `TODO` |
| `estimated_seconds` | INTEGER | ≥ 0 |
| `sort_order` | INTEGER | 当日排序 |
| `completed_at` | TIMESTAMPTZ | 可空 |
| `deleted_at` | TIMESTAMPTZ | 可空 |
| `created_at` | TIMESTAMPTZ | 创建时间 |
| `updated_at` | TIMESTAMPTZ | 更新时间 |

## `partnerships`

| 字段 | 类型 | 约束/说明 |
|---|---|---|
| `id` | UUID | PK |
| `requester_id` | UUID | FK → `users.id` |
| `addressee_id` | UUID | FK → `users.id` |
| `pair_key` | VARCHAR(73) | 两个 UUID 排序后的规范键 |
| `status` | `partnership_status` | 邀请状态 |
| `responded_at` | TIMESTAMPTZ | 可空 |
| `deleted_at` | TIMESTAMPTZ | 取消、拒绝或解除时软删除 |
| `created_at` | TIMESTAMPTZ | 创建时间 |
| `updated_at` | TIMESTAMPTZ | 更新时间 |

未删除的 `pair_key` 唯一，防止双方同时建立重复关系。

## `user_blocks`

| 字段 | 类型 | 约束/说明 |
|---|---|---|
| `id` | UUID | PK |
| `blocker_id` | UUID | FK → `users.id` |
| `blocked_id` | UUID | FK → `users.id` |
| `created_at` | TIMESTAMPTZ | 创建时间 |

`(blocker_id, blocked_id)` 唯一，且两者不得相同。

## `daily_plan_shares`

| 字段 | 类型 | 约束/说明 |
|---|---|---|
| `id` | UUID | PK |
| `daily_plan_id` | UUID | FK → `daily_plans.id` |
| `owner_id` | UUID | FK → `users.id` |
| `partner_id` | UUID | FK → `users.id` |
| `share_duration` | BOOLEAN | 是否公开计划/实际时长 |
| `deleted_at` | TIMESTAMPTZ | 撤销时软删除 |
| `created_at` | TIMESTAMPTZ | 创建时间 |
| `updated_at` | TIMESTAMPTZ | 更新时间 |

未删除的 `(daily_plan_id, partner_id)` 唯一。触发器验证计划所有者、有效伙伴关系和双向屏蔽。

## `encouragements`

| 字段 | 类型 | 约束/说明 |
|---|---|---|
| `id` | UUID | PK |
| `share_id` | UUID | FK → `daily_plan_shares.id` |
| `sender_id` | UUID | FK → `users.id` |
| `receiver_id` | UUID | FK → `users.id` |
| `encouragement_type` | `encouragement_type` | 固定选项 |
| `created_at` | TIMESTAMPTZ | 创建时间 |

## `notifications`

| 字段 | 类型 | 约束/说明 |
|---|---|---|
| `id` | UUID | PK |
| `user_id` | UUID | FK → `users.id`，通知接收者 |
| `actor_id` | UUID | 可空，FK → `users.id`，删除后置空 |
| `notification_type` | `notification_type` | 事件类型 |
| `payload` | JSONB | 事件关联 ID 和固定业务字段 |
| `read_at` | TIMESTAMPTZ | 可空 |
| `created_at` | TIMESTAMPTZ | 创建时间 |
| `updated_at` | TIMESTAMPTZ | 更新时间 |

## 外键关系摘要

```text
users 1─1 profiles
users 1─N tasks ── self parent
users 1─N sessions ── tasks / daily_plan_items
users 1─N daily_plans 1─N daily_plan_items ── tasks
users N─N users via partnerships
users N─N users via user_blocks
daily_plans 1─N daily_plan_shares ── partner users
daily_plan_shares 1─N encouragements
users 1─N notifications
```
