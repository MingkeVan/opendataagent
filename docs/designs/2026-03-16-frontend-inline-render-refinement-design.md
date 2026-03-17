# Frontend Inline Render Refinement Design

- 日期：2026-03-16
- 适用范围：`frontend/`
- 关联计划：[2026-03-16-frontend-inline-render-refinement-plan.md](/Users/guoruping/.codex/worktrees/4d77/opendataagent/docs/plans/2026-03-16-frontend-inline-render-refinement-plan.md)

## 1. 背景

当前未提交的大幅前端重构把界面拉成了更重的 control-room 形态，主要问题有三类：

- 右侧 `sandbox` 占比过高，偏离“在聊天框直接消费问数结果”的真实需求
- 边角处理过于锐利，工程感保留了，但界面显得僵硬
- 左侧 explorer 过窄，导致标题、状态和时间容易发生挤压或换行

本次调整不追求重新设计一套新界面，而是回到已经验证过的稳定基线，在其上完成小范围修复。

## 2. 目标

- 回到更克制的两栏问数界面
- 数据结果直接在聊天流中消费，而不是强依赖右侧面板
- 保留现有后端协议、SSE 流和 `uiParts` 结构
- 在不破坏产品工程感的前提下，让边角和组件轮廓更柔和

## 3. 非目标

- 不改后端 API
- 不改 SSE 协议或 `uiParts` 数据结构
- 不新增信息栏、筛选器、快捷操作面板等新交互层
- 不恢复 `data-artifact` 的单独详情查看能力

## 4. 布局决策

- 整体改为两栏：
  - 左侧 `Explorer`
  - 右侧主聊天区
- 左侧 explorer 宽度从 `w-64` 提升到 `w-72`
- 主聊天区接管原来右侧 `sandbox` 的展示职责
- 右侧 `sandbox` 整列完全移除

## 5. 渲染决策

- `text`：继续正常渲染
- `reasoning` / `tool-call`：继续留在折叠的 `Thinking Process`
- `data-table`：直接在 assistant 消息下方渲染 `el-table`
- `data-chart`：直接在 assistant 消息下方渲染 `VChart`
- `data-artifact`：仅保留摘要卡片，不提供详情跳转

## 6. 视觉决策

- 保持蓝白灰主色和 1px 硬边界
- 去掉全局强制直角覆盖
- 按钮、输入框、会话项、结果卡片、`details` 使用 `rounded-sm` 或 `rounded-md`
- 用户消息气泡继续保留更明显的圆角
- 保持无阴影结构分隔，不走柔和卡片化方向

## 7. 状态与兼容性

- 空状态、运行中、错误态、无消息态沿用现有结构，只调整文案使其符合内联结果模式
- 前端继续使用当前 `useChat` 和 SSE 合流逻辑
- 删除仅服务 `sandbox` 的前端状态，但不改后端任何接口
- `data-artifact` 仍可从后端产出，只是前端本轮不再主动拉取详情
