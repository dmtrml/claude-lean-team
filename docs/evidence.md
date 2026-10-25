# Evidence log

Measurements behind the rules, with the project and step they come from. Rules in the skill cite this file; new measurements are appended here (newest first within each section). A rule earns its place in the core only through repeated evidence (see the skill's "Learn from every iteration" section).

Rules written before version 2.0 are kept as they were (grandfathered) and are re-validated as new evidence arrives.

## Cases

### The learning loop itself (audit of 2.1.0, 2026-10-25) → version 2.2
- **Data:** 52 metric lines (2026-10-16…24) from 4 projects (video production 38, web backend 9, web game 4, document check 1), 58 candidates, 2 project layers, 45 session logs that mention the skill.
- **Who turned the skill on:** the user's `/lean-team` in 11 sessions, a parent session's brief ("first load /lean-team") in ~25, the model on its own in 3. In 6 more the user asked to save tokens and the skill was never loaded.
- **Consolidation:** 0 runs in 52 iterations (the core asked for one every ~5). The personal layer was never created; one project layer grew to 66 lines (cap 40) and held measurements, not rules. Duplicate candidate ids appeared.
- **Promotion:** 2 of 58 candidates in 9 days, although several were applied 3–5 times — thresholds could not be counted: metric lines used 89 different fields (`tool_calls` / `tool_calls_approx` / `tool_uses`), 8 had no skill version.
- **Cost drift:** the candidates file reached 29 KB (≈ 8–9k tokens when read whole).
- **Session-log detail for token counts:** one model call is written once per content block with the same `usage` (up to 7 lines per call); counting lines instead of `message.id` roughly doubles the total.
- **2.2 response:** hooks that remind at session start and on "save tokens" prompts; `lt.sh tokens` (deduplicated counts from the session log); `lt.sh log` (one schema, validated ids); `lt.sh status` (thresholds, retire list, consolidation due, size caps); strict candidate format. Expected: the skill is loaded in most multi-step sessions without the user typing it, and consolidation runs every ~5 iterations. To be re-measured on the next 10 iterations.

### YT_G (FastAPI/SQLite backend, Windows + WSL, 2026-10-15), step RS-5.3 review fixes
- **Executors:** Codex `gpt-6.1-sol` as builder (2 runs, ~216k tokens) and as independent read-only reviewer (5 runs, ~385k tokens); Antigravity Gemini 3.8 Flash High as builder for the next step (~30–40 min, no terminal access). Claude did planning, briefs, diff review and the Windows/WSL gates.
- **Four review rounds instead of 1–2:** ~40 % of the Codex tokens of the step went to rounds 2–4. Causes: `brief-ambiguous` (invariants listed as example encodings instead of a principle), `design-not-decided` (the builder chose a global logging patch), `ownership-too-narrow` (the error-code fix needed a file outside the allowed list), `brief-contradictory` ("keep all round-1 tests" while replacing that design), `scope-grew-in-review` (new leak channels each round), `lead-error` (one gap in the lead's own fix).
- **Antigravity cold start:** a one-line prompt cost 24 246 input tokens and 9 s (agy 1.3.5).

### Archipelago (web game, 2026-10)
- **Contract in code before parallel agents** (engagement step): engine 17 min ∥ UI 6.5 min, zero collisions; translations ran last over the placeholders.
- **Tiny check output:** 8.3k → 0.74k chars per run per agent (−91%).
- **Layout regressions agents missed:** a new block pushed the weekly summary off a 768-px screen; one extra header button hid the week number on a phone.
- **Codex on Windows:** with `[windows] sandbox = "elevated"`, Codex ran `npm`, `tsc`, `vitest` and the simulator fine (4 runs).
- **Antigravity (Gemini 3.8 Flash High) profile:** small tasks 6–14 min and 40–47k thinking tokens; clean translation of 82 i18n strings; a header widget ignored the phone width.

### Fogbury (web game, step 4b)
- 3 parallel Codex `gpt-6.1-sol` runs built 3D locations from a brief + example modules (5–7 min each), then 2 sequential runs authored 7 bilingual units that passed `content:check` first time.
- Claude weekly usage **+2 pp** vs **+9 pp** for a comparable Claude-only step; ~94 % of Codex input was cached.

## Open candidates (public examples; each needs more evidence before it becomes a rule)

### C1: For risky or core code, the lead fixes the design and the invariants before delegating
- Action: state the design choice (e.g. "credentials never enter the HTTP client layer; inject them in the transport"); write invariants as principles and test them with generated inputs, not example lists; give file ownership along the whole call path; list the old tests a design change replaces; agree the threat model and the review stop criterion before round 1.
- Expected effect: review rounds per step ≤ 2.
- Status: candidate (1 observation: YT_G RS-5.3).

### C2: Prefer a Claude Haiku subagent over an external executor for short lookups
- Action: when a task is smaller than an executor's fixed start cost (see its adapter's measured profile), use the Claude worker tier even if the executor has headroom.
- Expected effect: lower lead verification time and tokens per short task.
- Status: candidate (1 observation: Antigravity cold start 24k tokens, YT_G 2026-10-15).

### C3: External executors first, by default (user policy, 2026-10)
- Action: §2a delegation order.
- Expected effect: Claude weekly % per comparable step falls.
- Status: trial (Fogbury step 4b: +2 pp vs +9 pp). Needs ≥ 2 more comparable steps.
