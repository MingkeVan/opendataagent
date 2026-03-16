# 基于 Skill 管理的通用 Agent 平台任务清单与执行记录

- 日期：2026-03-13
- 状态：全部任务已完成并验证
- 依赖文档：[2026-03-13-skill-driven-agent-platform-design.md](/Users/guoruping/.codex/worktrees/f5b1/opendataagent/docs/designs/2026-03-13-skill-driven-agent-platform-design.md)
- 技术基线：`Vue 3 + Element Plus + TailwindCSS + Vite + AI SDK + Python FastAPI + Claude Agent SDK Adapter + MySQL`
- 基础设施约束：仅使用本地 Docker MySQL，新建 schema `opendata_agent`；不引入 Redis、Celery、对象存储

## 1. 执行原则

- 计划文档以可执行 task 为单位，而不是只保留阶段性描述
- 每个 task 必须明确交付物、完成状态和验证方式
- 所有 task 完成后，必须通过后端测试、前端构建和浏览器联调
- 仅提交必要文件；构建产物、临时日志、数据库文件、浏览器调试痕迹不提交

## 2. Task 总览

### 2.1 文档与目录

- [x] 创建 `docs/designs`
- [x] 创建 `docs/plans`
- [x] 输出平台设计文档
- [x] 输出任务清单与执行记录文档

交付结果：

- [2026-03-13-skill-driven-agent-platform-design.md](/Users/guoruping/.codex/worktrees/f5b1/opendataagent/docs/designs/2026-03-13-skill-driven-agent-platform-design.md)
- [2026-03-13-skill-driven-agent-platform-plan.md](/Users/guoruping/.codex/worktrees/f5b1/opendataagent/docs/plans/2026-03-13-skill-driven-agent-platform-plan.md)

验证方式：

- 文档路径和命名符合 `yyyy-MM-dd-*.md`
- 文档内容覆盖架构、schema、接口、任务、风险和验收

### 2.2 Skill 文件规范

- [x] 定义 `skills/<skill-id>/skill.yaml + prompt.md + assets/` 规范
- [x] 定义 `SkillManifest` 最小字段集合
- [x] 提供可加载的示例 skill
- [x] 实现 skill loader 与 reload 能力

交付结果：

- [skill.yaml](/Users/guoruping/.codex/worktrees/f5b1/opendataagent/skills/demo-analyst/skill.yaml)
- [prompt.md](/Users/guoruping/.codex/worktrees/f5b1/opendataagent/skills/demo-analyst/prompt.md)
- [skill_loader.py](/Users/guoruping/.codex/worktrees/f5b1/opendataagent/backend/app/services/skill_loader.py)

验证方式：

- `GET /api/skills` 返回示例 skill
- `GET /api/skills/{skillId}` 返回完整 manifest
- `POST /api/admin/skills/reload` 可重新扫描本地 skill

### 2.3 MySQL Schema 与持久化

- [x] 建立 `opendata_agent` schema 初始化逻辑
- [x] 定义 `conversations`
- [x] 定义 `messages`
- [x] 定义 `runs`
- [x] 定义 `run_events`
- [x] 定义 `tool_calls`
- [x] 定义 `artifacts`
- [x] 定义 `skill_snapshots`
- [x] 实现 `messages.raw_blocks` 原样存储
- [x] 实现 `messages.ui_parts` 渲染快照存储
- [x] 实现 `run_events` append-only 事件流

交付结果：

- [entities.py](/Users/guoruping/.codex/worktrees/f5b1/opendataagent/backend/app/models/entities.py)
- [init_schema.py](/Users/guoruping/.codex/worktrees/f5b1/opendataagent/backend/app/db/init_schema.py)
- [session.py](/Users/guoruping/.codex/worktrees/f5b1/opendataagent/backend/app/db/session.py)

验证方式：

- 应用启动时自动建表
- 发送消息后可在 MySQL 中看到 conversation、message、run、run_event 记录
- assistant 完成后可看到聚合后的 `ui_parts`

### 2.4 API 网关

- [x] 实现 `GET /api/skills`
- [x] 实现 `GET /api/skills/{skillId}`
- [x] 实现 `POST /api/admin/skills/reload`
- [x] 实现 `POST /api/conversations`
- [x] 实现 `GET /api/conversations`
- [x] 实现 `GET /api/conversations/{id}`
- [x] 实现 `GET /api/conversations/{id}/messages`
- [x] 实现 `POST /api/conversations/{id}/messages`
- [x] 实现 `GET /api/runs/{runId}/stream?after_seq=`
- [x] 实现 `POST /api/runs/{runId}/cancel`

交付结果：

- [main.py](/Users/guoruping/.codex/worktrees/f5b1/opendataagent/backend/app/main.py)
- [skills.py](/Users/guoruping/.codex/worktrees/f5b1/opendataagent/backend/app/api/routes/skills.py)
- [admin.py](/Users/guoruping/.codex/worktrees/f5b1/opendataagent/backend/app/api/routes/admin.py)
- [conversations.py](/Users/guoruping/.codex/worktrees/f5b1/opendataagent/backend/app/api/routes/conversations.py)
- [runs.py](/Users/guoruping/.codex/worktrees/f5b1/opendataagent/backend/app/api/routes/runs.py)

验证方式：

- FastAPI 本地启动成功
- 测试与浏览器联调都走上述接口，不依赖 mock HTTP 层

### 2.5 Worker 与执行隔离

- [x] 实现 MySQL run queue 轮询
- [x] 使用 `SELECT ... FOR UPDATE SKIP LOCKED` 领取 run
- [x] 建立 `EngineAdapter` 抽象
- [x] 为每个 run 启动独立子进程
- [x] 将子进程事件映射为标准化 `run_events`
- [x] 支持 cancel 标志检测和 run 终止
- [x] 预留真实 Claude Agent SDK 替换位

交付结果：

- [base.py](/Users/guoruping/.codex/worktrees/f5b1/opendataagent/backend/app/engines/base.py)
- [claude_agent_sdk.py](/Users/guoruping/.codex/worktrees/f5b1/opendataagent/backend/app/engines/claude_agent_sdk.py)
- [main.py](/Users/guoruping/.codex/worktrees/f5b1/opendataagent/backend/app/worker/main.py)
- [claude_agent_sdk_process.py](/Users/guoruping/.codex/worktrees/4d77/opendataagent/backend/app/runtime/claude_agent_sdk_process.py)

验证方式：

- 一个 active run 对应一个独立子进程
- 并发会话不会共享同一个长生命周期 SDK client
- worker 崩溃或子进程异常时 run 可标记为失败或中断

### 2.6 前端聊天台

- [x] 初始化 `Vue 3 + Vite + Element Plus + TailwindCSS`
- [x] 建立会话列表
- [x] 建立 Skill 切换器
- [x] 建立消息流区域
- [x] 建立输入区
- [x] 建立运行状态条
- [x] 建立 tool/artifact 详情抽屉

交付结果：

- [App.vue](/Users/guoruping/.codex/worktrees/f5b1/opendataagent/frontend/src/App.vue)
- [MessageCard.vue](/Users/guoruping/.codex/worktrees/f5b1/opendataagent/frontend/src/components/MessageCard.vue)
- [ChartCard.vue](/Users/guoruping/.codex/worktrees/f5b1/opendataagent/frontend/src/components/ChartCard.vue)
- [api.ts](/Users/guoruping/.codex/worktrees/f5b1/opendataagent/frontend/src/lib/api.ts)
- [stream.ts](/Users/guoruping/.codex/worktrees/f5b1/opendataagent/frontend/src/lib/stream.ts)

验证方式：

- 页面可创建并切换会话
- 页面可发送多轮消息并展示历史
- 刷新后能继续加载历史消息

### 2.7 Thinking、Tool、Chart、Table 渲染

- [x] 实现 `reasoning-*` parts 折叠展示
- [x] 实现 thinking timeline 视图
- [x] 实现 tool 五态 block
- [x] 实现 `data-table` 渲染
- [x] 实现 `data-chart` 渲染
- [x] 实现 `data-artifact` 占位与详情能力
- [x] 实现运行事件到 `UIMessage.parts` 的聚合

交付结果：

- [MessageCard.vue](/Users/guoruping/.codex/worktrees/f5b1/opendataagent/frontend/src/components/MessageCard.vue)
- [ChartCard.vue](/Users/guoruping/.codex/worktrees/f5b1/opendataagent/frontend/src/components/ChartCard.vue)
- [types.ts](/Users/guoruping/.codex/worktrees/f5b1/opendataagent/frontend/src/types.ts)

验证方式：

- reasoning 默认折叠
- tool 状态显示 `input-streaming`、`input-ready`、`running`、`output-ready`、`failed`
- 表格与图表都能实际渲染

### 2.8 刷新恢复与历史回放

- [x] 前端记录 `runId` 与最后消费的 `seq`
- [x] SSE 接口先回放 `after_seq` 之后的历史事件
- [x] run 未结束时继续 tail 新事件
- [x] 历史页面直接读取 `messages.ui_parts`

交付结果：

- [stream_service.py](/Users/guoruping/.codex/worktrees/f5b1/opendataagent/backend/app/services/stream_service.py)
- [run_service.py](/Users/guoruping/.codex/worktrees/f5b1/opendataagent/backend/app/services/run_service.py)
- [conversation_service.py](/Users/guoruping/.codex/worktrees/f5b1/opendataagent/backend/app/services/conversation_service.py)

验证方式：

- 页面刷新后能恢复历史和最新一次执行结果
- 第二轮消息完成后再次刷新，仍能回放完整内容

### 2.9 测试与联调

- [x] 编写后端集成测试
- [x] 运行后端测试并通过
- [x] 运行前端构建并通过
- [x] 使用浏览器做前后端联调
- [x] 验证全链路：创建会话 -> 发送消息 -> 流式展示 -> 历史回放 -> 刷新恢复

交付结果：

- [test_api_flow.py](/Users/guoruping/.codex/worktrees/f5b1/opendataagent/backend/tests/test_api_flow.py)
- [test_skill_loader.py](/Users/guoruping/.codex/worktrees/f5b1/opendataagent/backend/tests/test_skill_loader.py)

验证方式：

- 后端测试命令通过
- 浏览器联调命令通过
- 前端构建命令通过

### 2.10 Git 提交与远端推送

- [x] 忽略不需要提交的文件
- [x] 提交实现代码
- [x] 提交文档与前端细节修复
- [x] 推送到 GitHub 分支 `codex/mysql-agent-platform`

交付结果：

- GitHub 分支：`codex/mysql-agent-platform`

验证方式：

- `git status` 仅剩本次预期变更
- `git push` 成功

## 3. 已完成的关键验证

### 3.1 后端测试

执行命令：

```bash
PYTHONPATH=backend pytest backend/tests -q
```

结果：

- 已通过，当前为 `4 passed`
- 剩余告警为 FastAPI `on_event` 弃用提醒，不影响功能正确性

### 3.2 前端构建

执行命令：

```bash
cd frontend && npm run build
```

结果：

- 已通过
- 存在 bundle size 警告，但不影响运行

### 3.3 浏览器联调

联调范围：

- 创建会话
- 发送第一轮消息
- 展示 reasoning 折叠 block
- 展示 tool call block
- 展示 table/chart
- 打开详情抽屉
- 发送第二轮消息
- 刷新页面并确认历史回放与状态恢复

结果：

- 全链路通过
- 前后端联调可用

## 4. 不提交的文件

以下文件或目录不进入 Git：

- `frontend/dist/`
- `.playwright-cli/`
- 本地日志文件
- Python 缓存和测试缓存
- 本地数据库导出文件
- IDE 临时文件

## 5. 剩余非阻塞项

- FastAPI 启动事件可以后续迁移到 lifespan API，以消除弃用告警
- 前端可以继续做 chunk 拆分，以优化构建警告
- 当前默认运行器就是 `claude_agent_sdk_process`；测试与本地演示通过 fixture 数据模式复用同一条执行链，无需维护单独 mock 运行器

## 6. 结论

本任务清单中的所有 MVP task 已完成，且已经完成后端测试、前端构建和浏览器全链路验证。当前仓库状态满足继续开发真实 Claude Agent SDK 接入、权限体系和更多 skill 的前提条件。
