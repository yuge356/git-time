# 模块 2：层级任务与时间预算

## 本模块范围

- 创建课程、章节、小节、练习和项目实践等层级任务
- 修改任务标题、上级任务、预计学习时间和状态
- 软删除任务及其全部子任务
- `TODO`、`IN_PROGRESS`、`PAUSED`、`BLOCKED`、`DONE` 状态流转
- 80%、100%、150% 时间预算阈值计算
- 任务树所有权隔离和 PostgreSQL RLS
- 数据库级同所有者父子约束和防循环触发器
- 思维导图与标签两种项目视图，切换选择保存在浏览器本地
- 项目、模块和任务统一使用模态弹窗创建或编辑
- 节点折叠、拖拽调整层级、缩放平移、进度/优先级/截止日期展示
- 独立任务依赖边、带箭头虚线展示及循环依赖校验

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
migrations/versions/0008_structured_task_tree.py
migrations/versions/0010_task_map_metadata_and_dependencies.py
```

新增 `tasks` 表主要字段：

- `id`
- `owner_id`
- `parent_id`
- `title`
- `node_type`
- `priority`
- `due_date`
- `status`
- `estimated_seconds`
- `sort_order`
- `completed_at`
- `deleted_at`
- `created_at`
- `updated_at`

任务依赖保存在独立的 `task_dependencies` 表中，不嵌入思维导图布局。这样任务数据可以被思维导图、
标签、后续看板、日历和甘特图共同复用。服务端拒绝自身依赖、跨用户依赖和循环依赖。

## 项目页面交互

- 右上角“思维导图 / 标签”切换控制同一份任务数据的呈现方式。
- 思维导图从左向右展示父子关系，支持折叠、缩放、平移和依赖虚线。
- 标签视图纵向展示原有层级卡片，保留状态、进度、预算、计时和拖拽操作。
- 点击节点名称或更多菜单中的编辑操作，会打开居中的模态弹窗。
- 新建项目、模块或子任务也使用同一弹窗，不再把表单插入到节点下方。

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
