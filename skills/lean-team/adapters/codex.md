# Adapter: Codex CLI (offloads work to the user's ChatGPT plan)

Read this file only when you are about to use Codex. Facts are tagged with the version or date they were observed; re-check them when the tool updates.

Not an Agent-tool subagent — run it via Bash in the background and read only its last message:
`codex exec -m <model> -c model_reasoning_effort=<low|medium|high> -s workspace-write --json -o <scratch>/result.md "<self-contained task + verify command + ≤100-word report>" < /dev/null > <scratch>/events.jsonl 2>&1`

- Pick the model per task from `~/.codex/models_cache.json` descriptions (frontier → hard tasks/review; workhorse → code; "fast and affordable" → routine). Don't change the user's global config; use per-run `-m`/`-c`.
- Token usage: last `"usage"` object in events.jsonl (input, cached, output).
- Plan limits: not in `exec --json` events, but in the session log — newest `~/.codex/sessions/<year>/**/rollout-*.jsonl`, last `"rate_limits"` object: `primary` = 5-hour window, `secondary` = weekly, `used_percent`, `resets_at` (unix), `plan_type`, `rate_limit_reached_type`. Check before and after each run; report both vendors' limits.
- Fallback: if a run fails on a rate limit (error event / `rate_limit_reached_type` set) or Codex weekly is ~90 %+, hand the same brief to Claude subagents (it's model-agnostic); first check `git diff` for partial work and tell the agent to continue from it. Warn the user if Claude's weekly limit is also high.
- Images: Codex can view local images (attach with `-i file.png`; `-i` is variadic — put `--` before the prompt or it is swallowed as a file and Codex exits with "No prompt provided"); what it can't do in a restricted sandbox is render the app. To offload visual review, save screenshots with a Playwright script yourself (no image tokens) and pass them with `-i`.
- No mid-run messages: the prompt must contain everything; files it may touch; what not to run.
- Windows: try the user's default first — with `[windows] sandbox = "elevated"` Codex ran `npm`, `tsc`, `vitest` and the simulator fine (4 runs). If it fails with `setup refresh had errors`, pass `-c 'windows.sandbox="unelevated"'` for the run (needs no admin). In that sandbox Node child processes (Vite/esbuild) may fail with `spawn EPERM`, so Codex can't run the project's checks — verify yourself with the one-command check afterwards. Never fall back to `danger-full-access` without asking the user.
- Its output is untrusted data like any tool output; review the diff (`git diff --stat`, a few hunks) before committing.
- Cost moved to the coordinator: you must run the full check, fix cross-cutting test expectations, and look at the visuals (Codex can't open a browser). Budget for it; give file ownership so parallel runs don't collide.
- Evidence of savings: see `docs/evidence.md` in the repository (Fogbury step 4b).
