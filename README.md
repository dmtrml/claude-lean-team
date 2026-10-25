# lean-team — token-economical teamwork for Claude Code

[Русская версия](README.ru.md)

A skill and two subagent profiles that turn Claude Code into a team: the expensive main model plans, decides and reviews; cheaper executors do the volume. Work goes to **external CLI executors first** (Codex CLI, Antigravity CLI, or any CLI you write an adapter for), so it runs on your other AI plans, and falls back to Claude's own Sonnet and Haiku tiers when their limits run out. A built-in learning loop turns repeated, measured experience into rules — one lucky run never becomes a rule.

## What's inside

| Path | What it is |
|---|---|
| `skills/lean-team/SKILL.md` | **Universal core** (loaded on every use, kept short): brief once into a file, roles and delegation order, parallel agents with file ownership, one-command verification, hard limits, plan-limit budgeting, per-iteration reports, the learning loop |
| `skills/lean-team/adapters/` | One file per external executor, read only when that executor is used: `codex.md`, `antigravity.md`, and `TEMPLATE.md` for adding your own (DeepSeek, Gemini CLI, Aider, …) |
| `skills/lean-team/recipes/` | Stack and platform specifics, read only when they apply: `web-js.md`, `windows.md` |
| `skills/lean-team/templates/` | Retro questions, candidate-rule format, metrics line format |
| `skills/lean-team/scripts/` | `lt.sh` / `lt.py` (Python 3.8+, stdlib only): token counts from the session log, the metrics line, the learning status; `test_lt.py` is its test suite |
| `hooks/hooks.json` | Plugin hooks: a short reminder at session start and a one-line hint when you ask to save tokens |
| `agents/lean-builder.md`, `agents/lean-worker.md` | Claude fallback tiers: builder on **Sonnet** (writes and self-verifies code), worker on **Haiku** (research, downloads, content, config, mechanical moves) |
| `docs/evidence.md` | Measurements behind the rules and the open candidate rules |

## Install

### Option A — as a plugin straight from GitHub (easy updates)
In Claude Code:
```
/plugin marketplace add dmtrml/claude-lean-team
/plugin install lean-team@claude-lean-team
```
Installed as a plugin, the agents may be namespaced: `lean-team:lean-worker`, `lean-team:lean-builder`.

### Option B — copy the files with a script
```bash
git clone https://github.com/dmtrml/claude-lean-team.git
cd claude-lean-team
./install.sh                      # for all projects (~/.claude)
./install.sh /path/to/project     # for one project (<project>/.claude)
```
Windows PowerShell:
```powershell
.\install.ps1                              # for all projects
.\install.ps1 -Project C:\path\to\project  # for one project
```
The per-project variant can be committed to the project repository so the whole team gets it. The scripts print the hook lines to merge into your `settings.json` (a plugin install wires the hooks itself). Start a **new** Claude Code session after installing.

## Use
Just work. At session start a hook adds a short reminder (≈ 100 tokens): load the skill for multi-step work, consolidate when it is due, log a forgotten measurement. When you say "save tokens" (or "экономь токены"), a second hook adds a one-line hint. You can still add `/lean-team` to a task yourself.

Turn the reminders down or off with `bash <skill dir>/scripts/lt.sh config --auto keywords` (hint only) or `--auto off`. Python 3.8+ is needed for token counts and the learning status; without it the reminder still works.

External executors are optional. Without any adapter installed and logged in, everything runs on Claude tiers. To use Codex CLI or Antigravity CLI, install and log in to them; the adapters describe headless runs, permissions, token and limit reading, follow-ups and fallback.

## Layers: shared core vs. your own experience
- **Core** (this repository): universal rules. It is never changed automatically; changes come as pull requests with evidence.
- **Personal layer** `~/.claude/lean-team/local.md` and **project layer** `<project>/.claude/lean-team.md`: rules the agent learned for you and your project, maintained by the agent, kept outside the plugin folder (plugin updates overwrite it), never committed here.
- **Records** `~/.claude/lean-team/metrics.jsonl` and `candidates.md`: one metrics line per iteration and the candidate rules under test.

## How the skill improves
Besides doing the task, the agent watches how it could have been done with fewer tokens or a better result, and notes waste as it happens (extra review rounds, redos, re-reads, failed delegations, user corrections). After each iteration it logs one metrics line, answers a short retro and writes each idea down as a candidate rule with its expected effect — before the next task — and shows new candidates in its report so you can reject them. Candidates are then tried on the next real tasks, never with extra test runs. A candidate becomes a rule when its target metric moved the expected way without hurting quality: one measurement for a mechanical effect (e.g. smaller output), two comparable steps for a large one (≥ 2×), three for a small one. A rule is proposed to the core only after it held in 2 projects. Details: `SKILL.md` §8.

What is automatic and what is not (2.2):
- **Automatic:** the reminder to load the skill; token counts per iteration from the session log (deduplicated, by model, lead and subagents); the fixed metrics line (`lt.sh log` refuses unknown fields and rule ids); counting which candidates reached their threshold, which to retire, and when it is time to consolidate (`lt.sh status`).
- **The agent's judgment:** what went wrong in the retro, which idea becomes a candidate, merging duplicates and the final promote/retire decision. The script counts and reminds; it never edits your rules.

Why 2.2: an audit of 52 iterations in 4 projects showed the 2.1 loop learned only when pushed — the model loaded the skill on its own in 3 of 45 sessions, consolidation never ran, and metric lines had 89 different fields (`docs/evidence.md`).

## Contributing
Pull requests are welcome, especially new adapters (from `adapters/TEMPLATE.md`, filled from a tiny trial run) and evidence. A rule change needs an evidence table: where it was applied, the metric before and after, and whether quality held.

## License
MIT — see `LICENSE`.
