---
name: Frontend UI Design Guidelines
description: Design and refine OpenDataAgent frontend interfaces with strong UX discipline and strict Style F conventions. Use when building, redesigning, or polishing Vue/Tailwind pages, chat surfaces, dashboards, inspectors, or other product UI in this repo.
---

# Frontend UI Design Rules

Use this skill for frontend work that needs more than surface-level beautification. The result should feel intentional, product-grade, and consistent with OpenDataAgent. This skill keeps the repo's Style F layout as the hard baseline while adding a stronger UX/design workflow before code is written.

## 0. Default Operating Mode

For this repo, default to **product mode**:

- Preserve the existing OpenDataAgent shell, interaction model, and data-heavy workflow.
- Treat Style F as a hard constraint, not a suggestion.
- Use the references at the end of this file when you need either project-specific rules or broader design heuristics.

Only break away from Style F if the user explicitly asks for a new visual direction.

## 1. Pre-Code Design Pass

Before editing code, decide these points in 3-6 bullets:

- Purpose: what user task gets easier or clearer?
- Context: who is using this and under what data density or time pressure?
- Direction: choose a concrete visual character such as `industrial`, `editorial analytical`, `control-room`, `quiet analytical`, or `brutalist utility`.
- Differentiation: what one or two details will make the interface feel intentional instead of generic?
- Constraints: responsiveness, accessibility, long text, overflow, streaming states, chart/table density, keyboard focus.

## 2. Core Principles (Non-Negotiable)
- **Pure Color Palette**: Use white (`#FFFFFF`) or light gray (`#FAFAFA`) for backgrounds. The primary interaction color is a professional/business blue (e.g., `#1677FF`, Tailwind's `blue-600` or `blue-700`).
  - **PROHIBITED**: Purple, magenta, gradients, neon colors, or anything that feels "magical" or commonly associated with AI consumer apps.
- **Zero/Minimal Border Radius**: Strongly prioritize `rounded-none` (0px) or `rounded-sm` (2px) to maintain a strict engineering/IDE aesthetic.
  - **EXCEPTION**: When rendering the "User" message bubble in the chat stream, use `rounded-lg` (8px) and a light blue background (`bg-blue-50`) to visually distinguish it from the agent.
- **No "AI-Flavor" Fluff**: Do NOT use glowing animations, particle particles, typewriter effects, or magic wand icons. Focus entirely on data presentation.
- **Hierarchy Over Ornament**: Solve clarity with typography, spacing, labels, and active states before adding decorative treatment.
- **Behavior First**: Preserve existing product behavior first, then refine presentation.

## 3. Layout Structure (Style F: Hybrid A+D)
The global layout must follow a strict, hard-bordered 3-column structure:
- **Left Column (Explorer)**: Fixed width (e.g., `w-64`). Contains the session list and skill selector. Flat and minimal.
- **Middle Column (Main Stage)**: The primary interaction zone. Contains the chat history stream and the bottom input block.
- **Right Column (Sandbox Inspector)**: Minimum `350px` width. This is a permanent data preview sandbox. 

### Bordering
- Separate all panes using simple `1px solid` borders (e.g., `border-gray-200` or `border-[#D9D9D9]`).
- Do NOT use soft shadows (`box-shadow`) to separate these panes. Use hard structural lines.

## 4. Chat Stream & Interaction Rules
- **Agent Output (Middle Pane)**:
  - Do not use a bounding card/bubble for the Agent. Let the text flow naturally.
  - **Thinking Process**: All `reasoning` and `tool_call` JSON must be encapsulated inside a native `<details>` HTML block (labeled "Thinking Process" or similar), so it is collapsed by default. Only the final `text` result is fully rendered.
  - **Artifacts/Charts**: Never render heavy tables or charts directly inside the middle chat stream. Instead, render a clean link/button (e.g., `[Inspect Data in Sandbox →]`).
- **User Output (Middle Pane)**:
  - Must be strictly distinguished. Align left (or flow normally) but wrap it in a bordered blue block (`bg-blue-50 border-blue-200`) with rounded corners (`rounded-lg`).
- **Sandbox Rendering (Right Pane)**:
  - When the user clicks an inspect link from the chat, the full data (JSON, Table, Echarts) is rendered entirely in the Right Column.

## 5. Implementation Rules

- Define or reuse a small token set before scattering colors, spacing, radii, and status styles.
- Improve empty, loading, error, streaming, selected, and disabled states; do not leave them as placeholders.
- Motion should be purposeful and sparse. Respect `prefers-reduced-motion`.
- On smaller screens, collapse or reorder panes intentionally; do not let the desktop layout fail passively.
- Dense data must remain readable under real content, not just placeholder examples.
- Avoid hover-only affordances for important actions.

## 6. Validation Checklist

- The primary action path is obvious in under 5 seconds.
- The active conversation, active run, and selected sandbox item are easy to identify.
- Long content wraps or truncates cleanly without breaking the layout.
- Tables, charts, JSON, and streamed content still fit the existing workflow.
- Focus states, contrast, and keyboard navigation still work.
- The page does not drift into generic consumer-AI aesthetics.

## References

- Project-specific shell and layout constraints: [references/open-dataagent-style-f.md](references/open-dataagent-style-f.md)
- Broader UI/UX heuristics for stronger visual decisions: [references/design-heuristics.md](references/design-heuristics.md)
