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
The per-project variant can be committed to the project repository so the whole team gets it. Start a **new** Claude Code session after installing.

## Use
Write your task and add `/lean-team`, or just say "save tokens". Until the skill is invoked it costs almost nothing (only its one-line description is in context).

External executors are optional. Without any adapter installed and logged in, everything runs on Claude tiers. To use Codex CLI or Antigravity CLI, install and log in to them; the adapters describe headless runs, permissions, token and limit reading, follow-ups and fallback.

## Layers: shared core vs. your own experience
- **Core** (this repository): universal rules. It is never changed automatically; changes come as pull requests with evidence.
- **Personal layer** `~/.claude/lean-team/local.md` and **project layer** `<project>/.claude/lean-team.md`: rules the agent learned for you and your project, maintained by the agent, kept outside the plugin folder (plugin updates overwrite it), never committed here.
- **Records** `~/.claude/lean-team/metrics.jsonl` and `candidates.md`: one metrics line per iteration and the candidate rules under test.

## How the skill improves
Besides doing the task, the agent watches how it could have been done with fewer tokens or a better result, and notes waste as it happens (extra review rounds, redos, re-reads, failed delegations, user corrections). After each iteration it logs one metrics line, answers a short retro and writes each idea down as a candidate rule with its expected effect — before the next task — and shows new candidates in its report so you can reject them. Candidates are then tried on the next real tasks, never with extra test runs. A candidate becomes a rule when its target metric moved the expected way without hurting quality: one measurement for a mechanical effect (e.g. smaller output), two comparable steps for a large one (≥ 2×), three for a small one. A rule is proposed to the core only after it held in 2 projects. Details: `SKILL.md` §8.

## Contributing
Pull requests are welcome, especially new adapters (from `adapters/TEMPLATE.md`, filled from a tiny trial run) and evidence. A rule change needs an evidence table: where it was applied, the metric before and after, and whether quality held.

## License
MIT — see `LICENSE`.
