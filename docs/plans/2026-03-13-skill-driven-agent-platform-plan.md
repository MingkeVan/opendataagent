# 基于 Skill 管理的通用 Agent 平台实施计划

- 日期：2026-03-13
- 状态：v1 实施计划
- 依赖文档：[2026-03-13-skill-driven-agent-platform-design.md](/Users/guoruping/.codex/worktrees/f5b1/opendataagent/docs/designs/2026-03-13-skill-driven-agent-platform-design.md)

## 1. 总体说明

本计划按五个阶段推进，目标是在尽量低的基础设施复杂度下，交付一个 MySQL-only 的通用 Agent 平台。每个阶段都必须满足四项完成定义：

- 有可演示链路
- 有最小集成测试
- 有失败场景处理
- 有数据库 schema 或接口变更说明

## 2. 交付原则

- 主执行路径固定为 `Claude Agent SDK`
- 存储只使用 `MySQL schema: opendata_agent`
- Skill 以文件为事实来源，数据库只保存快照
- 前端始终围绕 `UIMessage.parts` 渲染
- 运行时隔离通过子进程边界保证

## 3. Phase 0：基础骨架与契约

### 3.1 目标

建立可继续扩展的仓库骨架、文档目录、Skill 规范、数据库 schema 和 API 契约。

### 3.2 关键任务

- 创建 `docs/designs`、`docs/plans`
- 建立 `skills/<skill-id>/skill.yaml + prompt.md` 规范
- 定义 `SkillManifest`、`EngineAdapter`、`RunStatus`、`UiMessagePart` 类型约定
- 设计并评审 MySQL schema
- 约定 API 路径、请求/响应结构、错误码格式
- 输出最小本地开发方式：前端、API、Worker、MySQL

### 3.3 交付物

- 设计文档
- 计划文档
- MySQL DDL 草案
- OpenAPI 草案或接口说明
- 至少一个示例 skill 包

### 3.4 验收

- 团队对 schema 和接口命名达成一致
- Skill 文件结构能够表达工具权限和会话策略
- API 路由表完整且没有职责冲突

### 3.5 最小测试

- manifest 解析测试
- skill prompt 路径解析测试
- schema 创建脚本 dry-run 测试

### 3.6 风险与处理

- 风险：一开始接口命名不稳定，导致后续前后端返工
- 处理：Phase 0 结束前冻结 v1 API 路径和主要 JSON 字段

## 4. Phase 1：前端聊天台与 Parts 渲染

### 4.1 目标

完成聊天台骨架，支持会话列表、消息流、输入区、运行状态条、详情面板，以及基于 `UIMessage.parts` 的本地渲染。

### 4.2 关键任务

- 初始化 `Vue 3 + Vite + Element Plus + TailwindCSS`
- 建立页面布局和基础路由
- 实现消息列表、输入区、会话列表、Skill 切换器
- 建立 `parts renderer registry`
- 实现以下 renderer：
  - text
  - reasoning
  - tool
  - chart
  - table
  - artifact
- 引入 timeline 组件，按 `step` 聚合展示

### 4.3 交付物

- 可运行的聊天台页面
- 本地 mock 数据驱动的消息渲染
- reasoning 折叠卡片
- tool call 五态卡片

### 4.4 验收

- UI 可稳定渲染 text/reasoning/tool/data-chart/data-table/data-artifact
- 页面刷新后能重新加载历史消息快照
- Timeline 和详情抽屉交互可用

### 4.5 最小测试

- parts renderer 单元测试
- conversation/message store 测试
- 核心页面快照或组件渲染测试

### 4.6 风险与处理

- 风险：前端先用 mock 数据时，后续接真流可能结构不一致
- 处理：严格按设计文档中的 JSON `type` 协议构造 mock 事件

## 5. Phase 2：MySQL 持久化与事件流

### 5.1 目标

实现会话持久化、消息持久化、run 队列、append-only 事件流和基于 MySQL 的 SSE tailing。

### 5.2 关键任务

- 初始化 `FastAPI` 和数据库访问层
- 实现 `conversations/messages/runs/run_events/skill_snapshots` 的 ORM 模型
- 编写 schema migration 或初始化脚本
- 实现：
  - `POST /api/conversations`
  - `GET /api/conversations`
  - `GET /api/conversations/{id}`
  - `GET /api/conversations/{id}/messages`
  - `POST /api/conversations/{id}/messages`
- 在发送消息时创建 `queued run`
- 实现 `GET /api/runs/{runId}/stream?after_seq=`
- 完成 `run_events` 回放和 tail 逻辑

### 5.3 交付物

- 可用的本地数据库 schema
- 会话和消息 API
- 基于 MySQL 的 SSE 事件回放
- 历史消息读取接口

### 5.4 验收

- 创建会话后能写入数据库
- 发送消息后能产生 `queued run`
- SSE 接口能从 `after_seq` 回放事件
- 历史页面只依赖 `messages.ui_parts` 也可正确渲染

### 5.5 最小测试

- API 集成测试
- `run_events` 顺序性测试
- SSE 回放测试
- MySQL 异常时的错误码测试

### 5.6 风险与处理

- 风险：MySQL 轮询 tail 导致延迟偏高
- 处理：控制 polling 间隔、建立覆盖索引、单 run 单连接、结束即断流

## 6. Phase 3：Agent SDK Worker 与 Skill Loader

### 6.1 目标

完成基于 MySQL 队列的 Worker、Skill Loader、Agent SDK 子进程隔离和取消/重试链路。

### 6.2 关键任务

- 实现 `scheduler` 轮询 `runs(status=queued)`
- 使用 `SELECT ... FOR UPDATE SKIP LOCKED` 领取任务
- 实现 `ClaudeAgentSdkAdapter`
- 为每个 run 拉起独立子进程
- 把原始事件转换为标准化 `run_events`
- 实现 `GET /api/skills`
- 实现 `GET /api/skills/{skillId}`
- 实现 `POST /api/admin/skills/reload`
- 实现 `POST /api/runs/{runId}/cancel`
- 设计并实现 `retry`/`continue` 行为

### 6.3 交付物

- 可运行的 Worker
- 技能加载与 reload
- run 取消和中断恢复逻辑
- 子进程隔离机制

### 6.4 验收

- 并发两个 conversation 时不会共享执行上下文
- skill reload 后新 run 使用新版本快照
- run 被取消后状态和事件一致
- 子进程异常退出后 run 标记为 `interrupted`

### 6.5 最小测试

- 并发 run 领取测试
- 子进程启动/终止测试
- skill reload 测试
- run cancel 测试

### 6.6 风险与处理

- 风险：Agent SDK 存在跨会话串扰风险
- 处理：禁止共享 client，只走子进程隔离；把该点设为高优先级集成测试

## 7. Phase 4：高级交互与历史回放

### 7.1 目标

补全 thinking 时间线、tool call block、chart/table/artifact 渲染和历史回放体验。

### 7.2 关键任务

- 完善 `reasoning-*` 渲染和默认折叠规则
- 在 timeline 中串联 `step/reasoning/tool/artifact/finish`
- 完善 tool card 的输入、执行、输出、失败状态
- 实现 `artifacts` 读写与详情展示
- 定义 `256KB` 阈值逻辑
- run 结束后聚合 `run_events -> messages.ui_parts`
- 保存 `messages.raw_blocks`

### 7.3 交付物

- reasoning 时间线
- tool 五态卡片
- chart/table/artifact 统一渲染
- 历史消息快照聚合逻辑

### 7.4 验收

- 历史回放和实时流展示一致
- thinking 默认折叠，但 timeline 能定位到具体 step
- 大型结果不会把消息区撑爆
- artifact 打开速度和体验可接受

### 7.5 最小测试

- reasoning timeline 组件测试
- tool state 迁移测试
- artifact 阈值测试
- history snapshot 聚合测试

### 7.6 风险与处理

- 风险：历史快照聚合逻辑和实时流展示不一致
- 处理：聚合逻辑复用同一套 parts normalizer，避免前后端各自解释

## 8. Phase 5：运维性、审计和扩展位

### 8.1 目标

完善审计、错误恢复、性能优化和第二执行引擎适配位，为后续演进做准备。

### 8.2 关键任务

- 建立结构化日志
- 实现按 `conversation_id/run_id/tool_call_id` 检索
- 增加关键指标埋点
- 设计 `run_events` 归档策略
- 设计 `artifacts` 清理策略
- 明确 `Messages API adapter` 需要实现的接口和差异点
- 增加压测和长会话测试

### 8.3 交付物

- 审计查询能力
- 基础监控指标
- 数据清理与归档建议
- 第二执行引擎的适配清单

### 8.4 验收

- 能定位一次失败 run 的完整轨迹
- 能看到 run 排队时间、总耗时、tool 成功率
- 历史事件与 artifact 增长可被观测和治理
- 新执行引擎的接入点明确且不影响前端协议

### 8.5 最小测试

- 审计检索测试
- 失败恢复测试
- 长会话性能测试
- 大量 `run_events` 分页测试

### 8.6 风险与处理

- 风险：单库同时承担业务库和事件流，增长过快
- 处理：建立归档策略、分表预案和未来外置存储替换位

## 9. 全局测试清单

- 会话创建、消息发送、历史加载、多轮对话连续性
- 刷新页面后通过 `after_seq` 回放并继续接收新事件
- thinking block 折叠展示正确，原始块和签名未被改写
- tool call 五态流转正确，失败与取消状态可回放
- chart/table 结果可由 `data-*` parts 或 artifact 正确渲染
- skill 文件修改后可 reload，非法 manifest 会被拒绝
- 并发两个 conversation 时不会共享 Agent SDK 上下文
- MySQL 临时异常时 API、Worker、前端返回一致错误语义

## 10. 建议的执行顺序

1. 先冻结 schema 和 API，再开前后端并行开发。
2. 前端先用标准协议 mock 数据完成渲染层。
3. 后端先打通 `conversation -> run -> run_events -> stream` 空链路。
4. 然后接入真实 Agent SDK，再补 reasoning/tool/artifact。
5. 最后处理审计、性能和第二执行引擎扩展位。

## 11. 阶段完成门槛

只有满足以下条件，才能进入下一阶段：

- 当前阶段核心链路可演示
- 对应最小测试已通过
- 失败场景有明确处理
- 数据库或接口变化已记录
- 不引入对下一阶段的结构性返工
