# 整体架构

## 1. 分层

```text
浏览器
├─ Vue 页面与组件
├─ Pinia 业务状态
├─ Axios HTTP / WebSocket
└─ Dexie IndexedDB
   ├─ 计时快照与 Session 待同步队列
   ├─ 任务、每日计划缓存
   └─ 任务/计划有序操作队列
          │
          ▼
FastAPI
├─ API 路由：认证、任务、计时、计划、统计、伙伴、分享、通知
├─ Pydantic：请求验证与响应边界
├─ Service：所有权、状态机、预算、聚合、分享权限
└─ SQLAlchemy Async：事务和数据访问
          │
          ▼
PostgreSQL
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
独立有向边。项目页面只负责把同一份数据渲染成“思维导图”或“标签”视图，因此以后增加看板、日历、
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

## 3. 安全边界

- 密码使用 Argon2 哈希，访问令牌使用带过期时间的 JWT。
- 浏览器不持有数据库凭据。
- 每次认证请求设置事务级 `app.current_user_id`。
- PostgreSQL RLS 限制账户、任务、Session、计划、伙伴、分享、鼓励和通知可见范围。
- API 服务层重复检查所有权、伙伴状态和屏蔽状态，形成应用层与数据库层双重约束。
- CORS 来源、JWT 密钥和数据库连接均从环境变量读取。

## 4. 前后端模块

| 前端 | 后端 |
|---|---|
| 登录、注册、资料 | auth、profiles |
| 思维导图/标签任务视图、弹窗编辑、预算提示 | tasks、task service |
| 计时器、历史、离线队列 | sessions、session state machine |
| 今日计划、打卡 | daily plans、check-ins |
| 统计图表 | analytics |
| 伙伴与屏蔽 | partnerships、blocks |
| 分享与鼓励 | plan shares、encouragements |
| 通知中心 | notifications、WebSocket |
| IndexedDB 同步 | 幂等客户端 UUID API |
