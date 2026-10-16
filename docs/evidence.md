# Evidence log

Measurements behind the rules, with the project and step they come from. Rules in the skill cite this file; new measurements are appended here (newest first within each section). A rule earns its place in the core only through repeated evidence (see the skill's "Learn from every iteration" section).

## Cases

### Archipelago (web game, 2026-10)
- **Contract in code before parallel agents** (engagement step): engine 17 min ∥ UI 6.5 min, zero collisions; translations ran last over the placeholders.
- **Tiny check output:** 8.3k → 0.74k chars per run per agent (−91%).
- **Layout regressions agents missed:** a new block pushed the weekly summary off a 768-px screen; one extra header button hid the week number on a phone.
- **Codex on Windows:** with `[windows] sandbox = "elevated"`, Codex ran `npm`, `tsc`, `vitest` and the simulator fine (4 runs).
- **Antigravity (Gemini 3.8 Flash High) profile:** small tasks 6–14 min and 40–47k thinking tokens; clean translation of 82 i18n strings; a header widget ignored the phone width.

### Fogbury (web game, step 4b)
- 3 parallel Codex `gpt-6.1-sol` runs built 3D locations from a brief + example modules (5–7 min each), then 2 sequential runs authored 7 bilingual units that passed `content:check` first time.
- Claude weekly usage **+2 pp** vs **+9 pp** for a comparable Claude-only step; ~94 % of Codex input was cached.
