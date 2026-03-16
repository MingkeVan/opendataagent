---
name: Frontend UI Design Guidelines
description: Strict guidelines for designing and implementing frontend UI components in the OpenDataAgent platform, following the finalized Style F (Hybrid A+D) conventions.
---

# Frontend UI Design Rules

When assigned a task to create or modify frontend UI components (Vue 3 / Tailwind CSS) for this project, you MUST strictly adhere to the following design principles. These rules have been finalized as the definitive "Style F" layout.

## 1. Core Principles (Non-Negotiable)
- **Pure Color Palette**: Use white (`#FFFFFF`) or light gray (`#FAFAFA`) for backgrounds. The primary interaction color is a professional/business blue (e.g., `#1677FF`, Tailwind's `blue-600` or `blue-700`).
  - **PROHIBITED**: Purple, magenta, gradients, neon colors, or anything that feels "magical" or commonly associated with AI consumer apps.
- **Zero/Minimal Border Radius**: Strongly prioritize `rounded-none` (0px) or `rounded-sm` (2px) to maintain a strict engineering/IDE aesthetic.
  - **EXCEPTION**: When rendering the "User" message bubble in the chat stream, use `rounded-lg` (8px) and a light blue background (`bg-blue-50`) to visually distinguish it from the agent.
- **No "AI-Flavor" Fluff**: Do NOT use glowing animations, particle particles, typewriter effects, or magic wand icons. Focus entirely on data presentation.

## 2. Layout Structure (Style F: Hybrid A+D)
The global layout must follow a strict, hard-bordered 3-column structure:
- **Left Column (Explorer)**: Fixed width (e.g., `w-64`). Contains the session list and skill selector. Flat and minimal.
- **Middle Column (Main Stage)**: The primary interaction zone. Contains the chat history stream and the bottom input block.
- **Right Column (Sandbox Inspector)**: Minimum `350px` width. This is a permanent data preview sandbox. 

### Bordering
- Separate all panes using simple `1px solid` borders (e.g., `border-gray-200` or `border-[#D9D9D9]`).
- Do NOT use soft shadows (`box-shadow`) to separate these panes. Use hard structural lines.

## 3. Chat Stream & Interaction Rules
- **Agent Output (Middle Pane)**:
  - Do not use a bounding card/bubble for the Agent. Let the text flow naturally.
  - **Thinking Process**: All `reasoning` and `tool_call` JSON must be encapsulated inside a native `<details>` HTML block (labeled "Thinking Process" or similar), so it is collapsed by default. Only the final `text` result is fully rendered.
  - **Artifacts/Charts**: Never render heavy tables or charts directly inside the middle chat stream. Instead, render a clean link/button (e.g., `[Inspect Data in Sandbox →]`).
- **User Output (Middle Pane)**:
  - Must be strictly distinguished. Align left (or flow normally) but wrap it in a bordered blue block (`bg-blue-50 border-blue-200`) with rounded corners (`rounded-lg`).
- **Sandbox Rendering (Right Pane)**:
  - When the user clicks an inspect link from the chat, the full data (JSON, Table, Echarts) is rendered entirely in the Right Column.

By following this skill, your generated Vue components will remain consistent, professional, and aligned with the chosen v1 aesthetic of the platform.
