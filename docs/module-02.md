# 模块 2：层级任务与时间预算

## 本模块范围

- 创建课程、章节、小节、练习和项目实践等层级任务
- 修改任务标题、上级任务、预计学习时间和状态
- 软删除任务及其全部子任务
- `TODO`、`IN_PROGRESS`、`PAUSED`、`DONE` 状态流转
- 80%、100%、150% 时间预算阈值计算
- 任务树所有权隔离和 PostgreSQL RLS
- 数据库级同所有者父子约束和防循环触发器
- 响应式任务树、任务编辑面板和预算展示

任务 API 保留了 `actual_seconds`、`budget_usage_ratio` 和 `budget_level` 字段。
模块 3 已接入 Session 聚合，以上字段现在返回真实学习时长和预算状态。

## 数据库迁移

```bash
cd backend
alembic upgrade head
```

新增迁移：

```text
migrations/versions/0002_hierarchical_tasks.py
```

新增 `tasks` 表主要字段：

- `id`
- `owner_id`
- `parent_id`
- `title`
- `status`
- `estimated_seconds`
- `sort_order`
- `completed_at`
- `deleted_at`
- `created_at`
- `updated_at`

## API

| 方法 | 地址 | 用途 |
|---|---|---|
| GET | `/api/v1/tasks` | 查询当前用户全部有效任务 |
| POST | `/api/v1/tasks` | 创建任务 |
| GET | `/api/v1/tasks/{task_id}` | 查询单个任务 |
| PATCH | `/api/v1/tasks/{task_id}` | 修改任务、父级、预算或状态 |
| DELETE | `/api/v1/tasks/{task_id}` | 软删除任务子树 |

所有接口都需要：

```text
Authorization: Bearer <access_token>
```

## 预算规则

```text
实际时间 / 预计时间 < 80%      NORMAL
实际时间 / 预计时间 >= 80%     NEAR_LIMIT
实际时间 / 预计时间 >= 100%    EXHAUSTED
实际时间 / 预计时间 >= 150%    SEVERE
```

预计时间为 0 时，预算等级为 `NOT_SET`。
