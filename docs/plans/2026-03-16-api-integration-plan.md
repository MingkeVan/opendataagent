# Frontend API Integration Implementation Plan
Date: 2026-03-16

## 目标 (Objective)
在前端 UI 风格定稿为 Style F 后，下一步是将 `useChat.ts` 中硬编码的假数据清理，实现与 `opendataagent` 后端 API 的全流程、零 Mock 对接，并确保所有更改安全合入代码库。

## 执行步骤 (Execution Steps)

1. **清理 Mock 数据层 (Clear Mock Data)**
   - 目标文件：`frontend/src/composables/useChat.ts`
   - 具体操作：将 `skills`, `conversations`, `messages` 的 `ref` 初始化从包含假数据的数组替换为完全空的数组 `[]`。
   - 验证：应用启动时，如果没有真实后端数据，页面应渲染为空白或提示文本，而非之前满屏的假对话流。

2. **验证 Typescript 与打包状态 (Verify Build)**
   - 在前端目录下运行 `npm run build`。
   - 确保修改 Mock 数据后，`useChat.ts` 及 `MainLayout.vue` 不会引起类型推导或空指针报错。

3. **代码清理与版本控制 (Version Control)**
   - 审查所新增/修改的文档是否正确：
     - `docs/designs/2026-03-16-frontend-ui-design.md` (已保留 Style F)
     - `docs/designs/2026-03-16-api-integration-design.md` (新增 API 设计文档)
     - 此计划文档本身。
   - 将所有前端的 `useChat.ts` 和 `App.vue` 变更加入 `git` stage。
   - 提交带有规范化 Commit Message 的 Git 提交。

## 成功标准 (Definition of Done)
1. 所有的文档都包含在 docs 文件夹内，并符合最新的需求。
2. 前端代码（剥离 Mock 后）可以顺利通过生产环境打包（`vite build`）。
3. 所有更改都成功提交到 Git 仓库，保持代码树整洁。
