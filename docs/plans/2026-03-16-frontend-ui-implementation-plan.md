# 前端 UI 实现计划 (v1 实施方案)

- 日期：2026-03-16
- 关联设计文档：`docs/designs/2026-03-16-frontend-ui-design.md`
- 关联架构文档：`docs/designs/2026-03-13-skill-driven-agent-platform-design.md`

## 1. 目标 (Objectives)
基于已确认的设计规范，在明确具体的界面风格（风格 A~E 中选定其一）后，实现一个无“AI 味”、蓝白色调、无大圆角，且参考重度数据工具布局的 Agent 平台前端。

## 2. 实施步骤 (Implementation Steps)

### 第 0 阶段：风格确认与设计冻结 (Phase 0: Style Confirmation)
1. **等待用户选择**：用户从设计文档 `docs/designs/2026-03-16-frontend-ui-design.md` 提供的 5 种预选界面风格（风格 A 到 风格 E）中进行选择。
2. **冻结细节**：选定后，明确最终的色值、边距、圆角参数。

### 第一阶段：项目脚手架与基础主题修改 (Phase 1: Foundation & Theming)的重构
1. **全局样式梳理**：
   - 移除现有库中偏向 C 端的默认大圆角设置 (修改 `tailwind.config.js` 或覆盖 Element Plus 变量)。
   - 定义标准的品牌蓝色 (如 `#1677FF`)，以及各种灰度背景色。
   - 检查和移除所有类似发光阴影、渐变色彩等“AI 感”的全局样式。
2. **核心 Layout 组件开发**：
   - `ChatLayout.vue`: **根据用户在第 0 阶段选择的风格（单栏/双栏/三栏、抽屉等），进行特定的结构重构**。包含会话区、状态区、交互区和预览区。

### 第二阶段：核心交互组件开发 (Phase 2: Core Interactivity Components)
1. **输入区 (Input Panel)**：
   - 使用带明显边框的 `textarea`。
   - 根据选定风格，配置操作按钮（是单一纯色按钮，还是带快捷菜单的复合操作台）。
2. **消息流模块 (Message Stream)**：
   - `UserMessage.vue` 和 `AssistantMessage.vue`。
   - 根据选定风格，应用其定义的消息区块展现形式（独立卡片 or 无框流式文本）。
3. **推理与工具调用模块 (Reasoning & Tool Call)**：
   - 根据 `UIMessage.parts` 数据结构，实现符合新风格的 `ThinkingCard.vue` 及拥有明确状态呈现流转的矩形卡片 `ToolBlock.vue`。

### 第三阶段：复杂数据呈现器 (Phase 3: Renderers)
1. **图表组件**：
   - 使用 `ECharts` 封装 `ChartRenderer.vue`。
   - 注入遵循蓝白主题的 ECharts theme json，去除过多网格线和不必要的渐变填充。
2. **表格组件**：
   - 基于 Element Plus `el-table` 的 `TableRenderer.vue`，设置为 `size="small"`，采用斑马纹，减小 padding 以提高信息密度。
3. **Artifact 审查面板 (Preview Drawer / Sandbox)**：
   - **具体取决于用户选定的风格（抽屉或永久沙盒）**，将大型表格和图表移至专属审查区。

## 3. 测试与验证计划 (Verification Plan)
1. **视觉回归验证 (Visual Review)**：
   - 在本地 `npm run dev` 启动后，人工检查全部组件的 `border-radius`、色值、对比度，确保符合选定风格规范。
2. **交互功能验证 (Interaction Testing)**：
   - 测试各类交互动作（Thinking 展开/折叠，Tool Call 状态流转），以及大型复杂数据的侧板/面板加载是否与选定风格的交互逻辑相符。
3. **集成验证 (End-to-End)**：
   - 连接真实的后端 API（或者内置 mock 数据），走通对话流并验证数据图表正常渲染。
