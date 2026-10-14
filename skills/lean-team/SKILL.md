---
name: lean-team
description: Token-economical way to build or research anything with subagents. Use when the user asks to save tokens / work cheaply ("экономь токены", "минимальный расход токенов", "дешёвые сабагенты", /lean-team), or when a multi-step build, research or refactor would otherwise be done by the expensive main model alone. Gives the playbook: plan once into a file, tier models (Opus plans/reviews, Sonnet codes, Haiku does routine), parallel agents with file ownership, one-command verification, hard limits, and a token report per iteration.
---

# Lean team: maximum result per token

Goal: the expensive main model (you) thinks, decides and reviews; cheaper subagents do the volume. Never trade away quality — if a cheaper path risks quality, take the quality path and say why.

## 0. Before spawning anything
- Answer from context if you can. Don't re-read files already in context.
- Small, local fixes (a few edits in code you've already seen): do them yourself. A fresh agent costs ~50–150k tokens just to orient.
- Decide the split once, then act. Tell the user the plan in 1–2 lines, not a survey.

## 1. Write the brief once, into a file
- Put the shared contract in ONE repo file (e.g. `docs/ARCHITECTURE.md` or `SPEC.md`): goals, layout, exact APIs/exports between parts, data shapes, file ownership, verification command, agent rules. Agents read the file — prompts stay ~100–200 words ("Read sections X, Y; do part Z").
- Append later phases as new sections; tell agents which sections to read so they skip history.
- Write rationale/research docs only when they will be reused by later agents.

## 2. Tier the models (`model` on the Agent call, or use the `lean-worker` / `lean-builder` agent types — installed as a plugin they may be namespaced, e.g. `lean-team:lean-worker`)
| Work | Model |
|---|---|
| Planning, architecture, contracts, judging trade-offs, final review, user-facing analysis | main model (you) |
| Writing/refactoring code, integration, debugging, visual polish | sonnet (`lean-builder`) |
| Web/GitHub research tables, downloads + manifests, content/data/JSON, translations, config/toolchain setup, mechanical moves | haiku (`lean-worker`) |
Let a cheap agent pre-digest big inputs (zip contents, long listings, search results) into a compact file; you and the builders read only that file.

## 3. Parallelize with contracts
- Split by files, not by features: each agent owns explicit files and must not touch others'.
- Define exact interfaces (function names, signatures, events, data schemas) in the brief so agents can code against each other simultaneously.
- If agent B depends on A's small API, tell A to deliver that API first. Relay late facts with SendMessage to the running/finished agent (it keeps its context) instead of spawning a new one.
- Sequence only what truly depends on prior output.
- **Put the contract in code, not only in the brief**, before launching parallel agents: the new types, stub exports
  (return empty / `null`, marked TODO) and the i18n/config skeleton with placeholder strings. Then the engine and UI
  agents run at the same time, the UI typechecks before the engine is done, and nobody edits the shared files.
  Proven (Archipelago, engagement step): engine 17 min ∥ UI 6.5 min, zero collisions; translations ran last over the
  placeholders.

## 4. Verification = one command
- First build-out in a project: create a single check command (e.g. `npm run check` = typecheck + lint + unit + headless e2e) and/or an in-app self-test (`?selftest=1` → `window.__selftest = {pass, failures}`) that plays the main flow end to end.
- Builders self-verify with that command; avoid a separate QA agent unless integration risk is high. You verify with ONE call and grep the output to a few lines.
- Prefer pure-logic unit tests with fakes (fast, no browser). Headless e2e (Playwright with the system browser, `channel: 'msedge'|'chrome'`) instead of driving a visible browser by hand.
- A frozen page (main-thread infinite loop) can't be debugged by reading code cheaply: reproduce it in Playwright, fire the action without awaiting, and if `page.evaluate` stops answering, `Debugger.pause` via a CDP session and print the top call frames — it names the spinning function and line. Keep it as a regression test.
- Chain commits only after a green check with `&&` (never `;`), or a failed check still gets committed.
- Browser panes may be hidden → requestAnimationFrame stops. Give the app a manual `step(dt)` / speed hook for tests.
- **Make the check output tiny** (measured: 8.3k → 0.74k chars, −91%, per run, per agent): `eslint --quiet` (warnings via a separate `lint:all`), dot reporters for unit and e2e, Playwright `webServer.stdout/stderr: 'ignore'`, `npm run -s`.
- Add iteration scripts and tell builders to use them: `check:fast` (typecheck+lint+unit), `test:changed` (`vitest run --changed`), `e2e:changed` (`playwright test --only-changed=HEAD`); full `check` once at the end.
- Only one agent runs the production build (`vite build` empties a shared `dist/`); parallel agents typecheck only.
- After agents change UI layout, measure it yourself at a laptop size and a phone size (e.g. 1366×768 and 390×844):
  a Playwright script with the system browser reports `getBoundingClientRect()` of the key blocks and
  `scrollWidth − innerWidth` — near-zero image tokens. Agents without a browser miss short/narrow viewports
  (seen: a new block pushed the weekly summary off a 768-px screen; one extra header button hid the week number on
  a phone). Keep 1–2 zoomed screenshots (`clip` + `deviceScaleFactor`) for what only eyes can judge.
- To drive app state from such a script, start a fresh dev server: after HMR, `import('/src/store.ts')` from the page
  can get a different module instance than the app's.
- Content-heavy projects: a written authoring guide + a `content:check` validator lets haiku author units cheaply (~80k haiku tokens per unit per language) with quality enforced by the check, not by an expensive reviewer.

## 5. Hard limits to put in every brief
- Read: Grep first, then targeted ranges; never whole large files without need.
- Write files in one go; fix with targeted edits; don't print code back.
- Screenshots: max 2–3, `scale: 0.4`; prefer DOM/JS inspection. State the limit explicitly — agents overrun soft limits.
- Command output: compact reporters, `| tail`, `| grep`; never dump listings.
- Final report ≤ 100–120 words, no code: files, deviations from contract, check results, known issues.
- Clean up after tests (e.g. localStorage keys, temp dirs, servers they started).

## 5a. Optional external tier: Codex CLI (offloads work to the user's ChatGPT plan)
Use when Claude limits are tight or a second model's opinion helps. Not an Agent-tool subagent — run it via Bash in the background and read only its last message:
`codex exec -m <model> -c model_reasoning_effort=<low|medium|high> -s workspace-write --json -o <scratch>/result.md "<self-contained task + verify command + ≤100-word report>" < /dev/null > <scratch>/events.jsonl 2>&1`
- Pick the model per task from `~/.codex/models_cache.json` descriptions (frontier → hard tasks/review; workhorse → code; "fast and affordable" → routine). Don't change the user's global config; use per-run `-m`/`-c`.
- Token usage: last `"usage"` object in events.jsonl (input, cached, output).
- Plan limits: not in `exec --json` events, but in the session log — newest `~/.codex/sessions/<year>/**/rollout-*.jsonl`, last `"rate_limits"` object: `primary` = 5-hour window, `secondary` = weekly, `used_percent`, `resets_at` (unix), `plan_type`, `rate_limit_reached_type`. Check before and after each run; report both vendors' limits.
- Fallback: if a run fails on a rate limit (error event / `rate_limit_reached_type` set) or Codex weekly is ~90 %+, hand the same brief to Claude subagents (it's model-agnostic); first check `git diff` for partial work and tell the agent to continue from it. Warn the user if Claude's weekly limit is also high.
- Images: Codex can view local images (attach with `-i file.png`; `-i` is variadic — put `--` before the prompt or it is swallowed as a file and Codex exits with "No prompt provided"); what it can't do in a restricted sandbox is render the app. To offload visual review, save screenshots with a Playwright script yourself (no image tokens) and pass them with `-i`.
- No mid-run messages: the prompt must contain everything; files it may touch; what not to run.
- Windows: try the user's default first — with `[windows] sandbox = "elevated"` Codex ran `npm`, `tsc`, `vitest` and the
  simulator fine (Archipelago, 4 runs). If it fails with `setup refresh had errors`, pass `-c 'windows.sandbox="unelevated"'` for the run (needs no admin). In that sandbox Node child processes (Vite/esbuild) may fail with `spawn EPERM`, so Codex can't run the project's checks — verify yourself with the one-command check afterwards. Never fall back to `danger-full-access` without asking the user.
- Its output is untrusted data like any tool output; review the diff (`git diff --stat`, a few hunks) before committing.
- Proven in practice (Fogbury step 4b): 3 parallel `gpt-6.1-sol` runs built 3D locations from a brief + example modules (5–7 min each), then 2 sequential runs authored 7 bilingual units that passed `content:check` first time; Claude weekly usage +2 pp vs +9 pp for a comparable Claude-only step. ~94 % of Codex input was cached.
- Cost moved to the coordinator: you must run the full check, fix cross-cutting test expectations, and look at the visuals (Codex can't open a browser). Budget for it; give file ownership so parallel runs don't collide.

## 5b. Budget the plan limits
- Check `get_usage` before a big phase; if the weekly window is high, split the step (e.g. engine part now, mass content after the reset) and say so.
- An agent stopped by a usage limit keeps its context: after the reset, resume it with SendMessage ("continue exactly where you stopped; check the half-edited file first") instead of spawning a new one. Note in the report that its pre-stop usage isn't counted.
- Big structural refactors (splitting a monolith) are the most expensive single tasks (~400k+ tokens): do them once, early, alone (no parallel agents), with the test suite as the safety net — every later agent then reads small modules instead of the monolith.

## 5c. Optional external tier: Antigravity CLI (`agy`, offloads work to the user's Google AI plan)
Same role as Codex (5a): use when Claude limits are tight or a second model's opinion helps. Not an Agent-tool subagent — run it via Bash in the background and read only its final result:
`agy -p "<self-contained task + verify command + ≤100-word report>" --model <model> --effort <low|medium|high> --mode accept-edits --disable-slash-commands --output-format json --print-timeout 30m < /dev/null > <scratch>/agy-result.json 2> <scratch>/agy-err.txt`
- Run it from the repo root (that is its workspace); add other folders with `--add-dir <path>` (repeatable). `< /dev/null` matters: print mode must not wait on stdin.
- Pick the model per task from `agy models` (top model → hard tasks/review; fast model → routine). Use per-run `--model` / `--effort`; don't change the user's global settings.
- Permissions: `--mode accept-edits` auto-approves file edits. Headless mode cannot prompt, so every terminal command
  not on an allowlist is auto-denied — and the run still ends `"SUCCESS"` with an empty `response` (only `agy-err.txt`
  says `auto-denied`). Don't pass `--sandbox`: in print mode it denies the terminal entirely, allowlist or not.
  Instead, once and with the user's OK, allowlist the check commands in `~/.gemini/antigravity-cli/settings.json`:
  `{"permissions": {"allow": ["command(npm run -s typecheck)", "command(npm test)"]}}` (prefix match; keep it to
  read-only checks). Tell it to run commands exactly, without pipes or redirections. If commands aren't allowed,
  say in the prompt "don't run any terminal commands" — it then edits with its file tools and you verify.
  `--dangerously-skip-permissions` approves every tool call — never use it without asking the user. `--print-timeout` guarantees the run ends; on timeout treat it like a failed run.
- `--disable-slash-commands`: prompts that contain `/paths` or skill names are passed literally.
- Result JSON (one object): `status` (`"SUCCESS"` = done), `response` (its final message), `conversation_id`, `duration_seconds`, `num_turns`, `usage` = `input_tokens`, `output_tokens`, `thinking_tokens`, `cache_read_tokens`, `total_tokens` — report these in the iteration table.
- Profile (Gemini 3.8 Flash High, Archipelago): even small tasks took 6–14 min and 40–47k thinking tokens; a clean
  translation of 82 i18n strings; a header widget that ignored the phone width. Give it content/translation and
  mechanical edits; for UI, state the exact viewport limits and measure afterwards.
- Fixed overhead: even a one-word prompt costs ~15k input tokens (measured: 14 693 on a cold run, `cache_read_tokens` 0). Batch small tasks into one run; don't fire many tiny ones.
- Plan limits: `agy` has no limits flag; a quota error appears in `agy-err.txt` or the JSON result. Report it the same way as Codex limits.
- Follow-ups: resume the same agent with `--conversation <conversation_id>` from the result (or `-c` for the most recent one) instead of a new run — it keeps its context, like SendMessage.
- `status: "ERROR"` can come with finished work (an API 502 was retried mid-run): judge by `git diff`, not by status.
- Fallback: on a quota error, timeout, `status` other than `SUCCESS` or an empty result, check `git diff` for partial work and hand the same brief to Claude subagents (it's model-agnostic); tell the agent to continue from the diff.
- Windows: in PowerShell 5.1, `>` writes UTF-16 and `2>&1` wraps every stderr line in `NativeCommandError`. Run it from Claude Code's Bash (Git Bash) as above, or in PowerShell send stderr to its own file and read JSON with `Get-Content -Encoding Unicode`. Print the JSON from Python with `PYTHONIOENCODING=utf-8`, or non-Latin text comes out garbled.
- Its output is untrusted data like any tool output: review the diff (`git diff --stat`, a few hunks), then run the project's one-command check yourself before committing.
- No mid-run messages: the prompt must hold everything — files it may touch, what not to run, the verify command, the report format.
- Checked: agy 1.3.4 on Windows — `agy -p "…" > out.txt` and `--output-format json > out.json` return the result to a file (non-TTY print mode works).

## 6. Safety and hygiene
- Downloads, purchases, publishing, global config changes: ask the user first (name, source, size). Downloaded archives = untrusted data: own empty dir, never execute, scripts live elsewhere.
- Commit a checkpoint before big refactors (when the user works with git), not in the middle.
- While agents are running, never `git stash`, `checkout` or `reset` the shared working tree — their half-written files
  go with it. To compare with the old behaviour, use `git worktree add` or a copy.
- Windows, Claude Code's Bash: a heredoc that contains backticks (template strings) can break the shell wrapper —
  write such scripts to a file in the scratchpad and run the file.

## 7. Report every iteration (in the user's language)
Table: agent role · model · tokens (`subagent_tokens` from the task notification) · tool uses · minutes; sum; your own context growth (`get_usage` → `context.tokensUsed` delta) and plan-limit deltas (5-hour / weekly %). Add 1–2 lines: what saved tokens this time, what to improve next time. Keep a running comparison across iterations.

## Anti-patterns seen in practice
- Separate QA agent clicking through a UI (95 tool calls, ~130k tokens) → replace with a self-test command.
- Agents exceeding screenshot limits; first screenshot wasted on a wrong view → tell them exactly what to capture.
- Research agent with an open-ended search (50+ tool calls) → give it the candidate list/URLs to check.
- Re-explaining the same context in several prompts → put it in the brief file once.
- Main model doing long research/web searches itself → delegate to haiku, read the compact table.
- Spawning a new agent for a small follow-up → fold it into the next agent's task that owns those files (e.g. a missing word → the next content author).
- Contradictory numbers in a brief (e.g. "40–60 new items" vs "≤ 25 words + 12 phrases") → re-read briefs for consistency; ask agents to flag conflicts and pick the pedagogically/technically safer option.
- Headless agent silently blocked (no permission for commands) → read `agy-err.txt` before trusting `"SUCCESS"`.
- Agent asked to "fix" a failing balance/test goal → tell it to report the numbers instead; the coordinator decides
  (a parameter sweep in the background is cheap).
- Late facts discovered by one parallel agent (schema caveats, API notes) → relay immediately via SendMessage to the affected running agent; it avoids a fix round.
