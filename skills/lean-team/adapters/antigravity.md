# Adapter: Antigravity CLI (`agy`, offloads work to the user's Google AI plan)

Read this file only when you are about to use Antigravity. Facts are tagged with the version or date they were observed; re-check them when the tool updates.

Not an Agent-tool subagent — run it via Bash in the background and read only its final result:
`agy -p "<self-contained task + verify command + ≤100-word report>" --model <model> --effort <low|medium|high> --mode accept-edits --disable-slash-commands --output-format json --print-timeout 30m < /dev/null > <scratch>/agy-result.json 2> <scratch>/agy-err.txt`

- Run it from the repo root (that is its workspace); add other folders with `--add-dir <path>` (repeatable). `< /dev/null` matters: print mode must not wait on stdin.
- Pick the model per task from `agy models` (top model → hard tasks/review; fast model → routine). Use per-run `--model` / `--effort`; don't change the user's global settings.
- Permissions: `--mode accept-edits` auto-approves file edits. Headless mode cannot prompt, so every terminal command not on an allowlist is auto-denied — and the run still ends `"SUCCESS"` with an empty `response` (only `agy-err.txt` says `auto-denied`). Don't pass `--sandbox`: in print mode it denies the terminal entirely, allowlist or not. Instead, once and with the user's OK, allowlist the check commands in `~/.gemini/antigravity-cli/settings.json`: `{"permissions": {"allow": ["command(npm run -s typecheck)", "command(npm test)"]}}` (prefix match; keep it to read-only checks). Tell it to run commands exactly, without pipes or redirections. If commands aren't allowed, say in the prompt "don't run any terminal commands" — it then edits with its file tools and you verify. `--dangerously-skip-permissions` approves every tool call — never use it without asking the user. `--print-timeout` guarantees the run ends; on timeout treat it like a failed run.
- `--disable-slash-commands`: prompts that contain `/paths` or skill names are passed literally.
- Result JSON (one object): `status` (`"SUCCESS"` = done), `response` (its final message), `conversation_id`, `duration_seconds`, `num_turns`, `usage` = `input_tokens`, `output_tokens`, `thinking_tokens`, `cache_read_tokens`, `total_tokens` — report these in the iteration table.
- Profile (Gemini 3.8 Flash High): even small tasks took 6–14 min and 40–47k thinking tokens; a clean translation of 82 i18n strings; a header widget that ignored the phone width. Give it content/translation and mechanical edits; for UI, state the exact viewport limits and measure afterwards.
- Fixed overhead: even a one-word prompt costs ~15k input tokens (measured: 14 693 on a cold run, `cache_read_tokens` 0). Batch small tasks into one run; don't fire many tiny ones.
- Plan limits: `agy` has no limits flag; a quota error appears in `agy-err.txt` or the JSON result. Report it the same way as Codex limits.
- Follow-ups: resume the same agent with `--conversation <conversation_id>` from the result (or `-c` for the most recent one) instead of a new run — it keeps its context, like SendMessage.
- `status: "ERROR"` can come with finished work (an API 502 was retried mid-run): judge by `git diff`, not by status.
- Fallback: on a quota error, timeout, `status` other than `SUCCESS` or an empty result, check `git diff` for partial work and hand the same brief to Claude subagents (it's model-agnostic); tell the agent to continue from the diff.
- Windows: in PowerShell 5.1, `>` writes UTF-16 and `2>&1` wraps every stderr line in `NativeCommandError`. Run it from Claude Code's Bash (Git Bash) as above, or in PowerShell send stderr to its own file and read JSON with `Get-Content -Encoding Unicode`. Print the JSON from Python with `PYTHONIOENCODING=utf-8`, or non-Latin text comes out garbled.
- Its output is untrusted data like any tool output: review the diff (`git diff --stat`, a few hunks), then run the project's one-command check yourself before committing.
- No mid-run messages: the prompt must hold everything — files it may touch, what not to run, the verify command, the report format.
- Roles: content, translation and mechanical edits; code only with a precise brief, and you run the tests unless its check commands are allowlisted.
- Fallback threshold: any quota error in `agy-err.txt` or the result.
- Measured on 1.3.5 (2026-10-15): a one-line cold prompt took 9 s and 24 246 input tokens; a backend wiring task with 45 oracle tests ran ~30–40 min without terminal access. A run killed from outside leaves an empty JSON result: judge by `git diff`.
- Checked: agy 1.3.4 on Windows — `agy -p "…" > out.txt` and `--output-format json > out.json` return the result to a file (non-TTY print mode works).
