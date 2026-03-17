# OpenDataAgent Style F

Use this reference when working on the main product UI.

## Core Visual Rules

- Backgrounds: `#FFFFFF` or `#FAFAFA`
- Primary accent: business blue such as `#1677FF`
- Avoid purple, magenta, neon, glassmorphism, soft gradients, and "magic AI" styling
- Border radius should be zero or minimal; only the user chat bubble may use a softer radius
- Use hard 1px borders to separate panes; do not rely on shadows for structure

## Layout

- Left column: explorer and skill selector, fixed width, flat presentation
- Middle column: chat stream and composer
- Right column: persistent sandbox/inspector for tables, charts, JSON, and artifacts
- Keep the three-pane layout structurally obvious

## Chat Behavior

- Agent output should read like a working surface, not a floating chat bubble wall
- Reasoning and tool traces should be collapsed by default with native affordances such as `<details>`
- Final answer text should remain visible and readable without opening debug content
- Large tables and charts should be inspected in the right pane instead of fully rendered in the stream
- User messages should remain visually distinct with a restrained blue treatment

## Component Tone

- Engineering product, not marketing site
- Crisp labels, compact density, clear status treatment
- Minimal ornament; hierarchy comes from typography, spacing, and borders

## Responsive Behavior

- Preserve usability on smaller screens by collapsing or stacking panes intentionally
- Avoid layouts that depend on hover alone
- Keep compose/send/inspect actions reachable without horizontal scrolling
