# OpenDataAgent API Integration Full Flow Design

## 1. 概览 (Overview)
Agent 架构要求前端和后台在“状态管理”与“实时增量信息展现”上具备极强的一致性。UI 设计要求使用 `useChat.ts` 作为一切通信的中枢。该文档详述如何通过真实的后端 API 将 UI 层与底层 Agent Engine 接通。

全局请求基础 URL 采用 `import.meta.env.VITE_API_BASE` 读取。

---

## 2. 交互流时序 (Interaction Sequence)

### A. 初始化加载阶段 (Initialization)
1. **获取可用技能模型**
   - **Endpoint**: `GET /api/skills`
   - **动作**: 页面 OnMounted 后，`loadSkills()` 方法拉取数据库/配置中的可用计算技能集合，渲染到顶部工具栏。
2. **获取会话历史**
   - **Endpoint**: `GET /api/conversations`
   - **动作**: `loadConversations()` 方法拉取该用户的所有历史对话，构建左侧 Explorer 层。若包含活动会话则继续轮询/恢复状态。

### B. 会话流转阶段 (Routing a Chat)
1. **新建/选中会话**
   - **新建**：`POST /api/conversations` (携带 `skillId`) -> 返回带有唯一 `Conversation.id` 的新对象。
   - **选中**：对于已存在的会话，点击后前端触发 `openConversation(id)`。
   - 依赖项：
     - `GET /api/conversations/{id}` (刷新会话元数据，如 Run 状态)
     - `GET /api/conversations/{id}/messages` (拉取完整聊天历史并预先渲染)

### C. 核心执行阶段 (Run Execution via SSE)
这是最关键、前后端交互要求最高的一环。
1. **发送新查询**
   - 前端包装用户的文本：`POST /api/conversations/{id}/messages`
   - Payload: `{ content: string }`
   - 响应内容不仅包含新的 MessageId，还要返回一个底层的调度ID：`{ runId: string }`
2. **启动 Server-Sent Events 流实时接收 Agent 回调**
   - 收到 `runId` 后立即切入 `startStream(runId)` 模式：建立长链 `EventSource: GET /api/runs/{runId}/stream`。
3. **数据流分拣 (Stream Payload Parsing)**
   - 后端每发回一条 SSE Payload，必须包含 `type`（如 `text`, `reasoning`, `tool-[action]`），及 `seq` 序列号保障不丢包。
   - 所有的流消息在前端实时被 `applyStreamEvent` 解析，通过 Vue 的深层响应式立刻合并展现在 `<details>`(思维逻辑面板) 或正常的 `div.markdown-body` (结果文本块) 内。
4. **终止请求**
   - 如果发生 Server-side 超时，SSE 发送 `[DONE]` 前会抛出 Error 类型的 payload。
   - 用户主动点选停止：`POST /api/runs/{runId}/cancel`。

---

## 3. 结构层约定 (Data Models)

前后端之间要求遵循严格的 JSON Typescript 推导：
- **`Conversation`**: `{'id', 'title', 'skillId', 'status', 'activeRunId', 'updatedAt'}`
- **`Message`**: `{'id', 'role': 'user'|'assistant', 'uiParts': [], 'status'}`
- **`UiPart`**: 聚合接口，通过 `type` 字段派生：
  - `type: 'text'` -> 携带推演得出的标准自然语言答复。
  - `type: 'reasoning'` -> 携带 Agent 内部思考摘要。
  - `type: 'tool_call'` -> 携带特定的工具指代 (`toolName`, `input`, `status`)。供前端右侧的 Sandbox Inspector 调用呈现。

## 4. 前端剥离 Mock 的后续处理
1. 清除 `useChat.ts` 中 `skills`, `conversations`, `messages` `ref` 对象内硬编码的假数据。
2. 彻底将初始值设为 `[]`。
3. 对接真实后端后执行严峻的 UI 状态断言检查（例如，当会话流为空且正在 `isSending` 时展示 Loading 骨架框架）。
