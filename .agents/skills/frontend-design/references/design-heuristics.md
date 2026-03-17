# Design Heuristics

Use this reference when the task allows stronger visual refinement beyond the default product shell.

## 1. Decide The Experience Before Coding

Write down:

- The user and the pressure they are under
- The task they must complete
- The visual direction
- The one memorable design detail
- The constraints that matter most

If these are unclear, the result usually becomes generic.

## 2. Pick A Specific Direction

Use concrete directions, not filler labels:

- `industrial utility`: hard edges, tight hierarchy, structural density
- `editorial analytical`: strong typography, grid rhythm, intentional contrast
- `control-room`: operational dashboards, emphasis on status and scanning
- `quiet analytical`: restrained palette, precise spacing, subtle authority
- `expressive data`: bold charts and contrast, but still product-grade

Pick one dominant direction and execute it consistently.

## 3. Typography

- Typography should do most of the visual work
- Use deliberate heading/body contrast
- Avoid default-feeling font stacks when the project allows a choice
- For OpenDataAgent surfaces, preserve the existing IBM Plex Sans stack unless there is a clear reason to change it

## 4. Color

- Use a constrained palette with clear semantic roles
- Prefer CSS variables or shared tokens
- Accent colors should support task focus, not novelty
- Keep contrast strong enough for dense enterprise UI

## 5. Motion

- Add motion only when it improves orientation or feedback
- Good uses: staged page load, panel reveal, hover emphasis, loading transitions
- Bad uses: constant shimmer, decorative motion everywhere, long easing that slows work

## 6. Composition

- Use scale, alignment, whitespace, and contrast to guide the eye
- Avoid dead-center sameness and evenly weighted panels when the task needs hierarchy
- Make selection, active state, and current context obvious

## 7. Productization Pass

Before you finish, check:

- empty states
- loading states
- error states
- overflow and truncation
- keyboard focus
- narrow-width behavior
- real data, not placeholder-only visuals
