# lean-team 2.2 — contract

Why: an audit of 52 iterations in 4 projects (2026-10-25) found that the skill learns only when pushed. The model loaded it on its own in 3 of 45 sessions; consolidation never ran; 2 of 58 candidates were promoted; metric lines had 89 different fields, so thresholds could not be counted. 2.2 adds hooks that turn it on, one script that measures tokens and writes a fixed metrics line, and a status that counts thresholds and says when to consolidate.

## 1. Files

| Path | Owner | What |
|---|---|---|
| `skills/lean-team/scripts/lt.py` | builder | the whole CLI, Python ≥ 3.8, stdlib only, one file |
| `skills/lean-team/scripts/test_lt.py` | builder | `unittest` suite, stdlib only, fixtures built in temp dirs |
| `skills/lean-team/scripts/lt.sh` | lead | launcher: first working Python 3.8+ (on Windows `python3` can be a Store stub that prints "Python" and exits 49) |
| `hooks/hooks.json` | lead | `SessionStart` → `lt.sh start`, `UserPromptSubmit` → `lt.sh prompt` |
| `SKILL.md`, `templates/*`, `README*`, `docs/evidence.md`, `install.*`, `.claude-plugin/plugin.json` | lead | texts and version 2.2.0 |

Check command (builder must leave it green): `python -I skills/lean-team/scripts/test_lt.py` — dot output, ≤ 20 lines. With `-I` the script dir is not on `sys.path`; the test inserts it itself.

## 2. Paths and environment

- `DATA` = env `LEAN_TEAM_HOME`, else `~/.claude/lean-team`. Inside: `metrics.jsonl`, `candidates.md`, `local.md` (personal layer), `state.json`, `config.json`, `sessions/` (per-session marker files). Create `DATA` only when writing.
- Transcripts root = env `LEAN_TEAM_PROJECTS_DIR`, else `$CLAUDE_CONFIG_DIR/projects`, else `~/.claude/projects`. A session's transcript: `<root>/*/<session_id>.jsonl` (if several, newest mtime). Its subagents: `<root>/<same folder>/<session_id>/subagents/*.jsonl`.
- Session id: `--session`, else env `CLAUDE_CODE_SESSION_ID`; for hooks, stdin JSON `session_id` (also `transcript_path`, `cwd`, and `prompt` for `UserPromptSubmit`).
- Project dir: `--project-dir`, else env `CLAUDE_PROJECT_DIR`, else hook stdin `cwd`, else `git rev-parse --show-toplevel` (timeout 2 s, errors ignored), else cwd. Project name = `--project` or the basename of the project dir. Project layer = `<project dir>/.claude/lean-team.md`.
- `VERSION = "2.2.0"` constant in `lt.py`. A test asserts it equals `version` in `<repo>/.claude-plugin/plugin.json` when that file exists three levels above the script.
- Always `sys.stdout.reconfigure(encoding="utf-8", errors="replace")` (and stderr). Print paths with forward slashes.
- `config.json`: `{"auto": "remind" | "keywords" | "off"}`; missing or invalid → `remind`.

## 3. Transcript parsing (shared by `tokens`, `log`, `start`)

- Read JSON lines; skip lines that fail to parse.
- A model call = a line with `type == "assistant"` and `message.usage`. One call is written once per content block with the same usage → **deduplicate by `message.id`** (keep the last line for that id). Skip `message.model == "<synthetic>"`.
- Per call: `input = usage.input_tokens`; `cache_read = usage.cache_read_input_tokens`; `output = usage.output_tokens`; cache writes from `usage.cache_creation.ephemeral_5m_input_tokens` and `ephemeral_1h_input_tokens`; if that object is missing, all `usage.cache_creation_input_tokens` count as 5m. Missing numbers = 0.
- `effective = input + 1.25 × write_5m + 2 × write_1h + 0.1 × cache_read + 5 × output` (input-price units, the same weights for every model; round to int at the end).
- Groups: `lead` = main transcript lines without `isSidechain: true`; `subagents` = main-transcript lines with `isSidechain: true` plus every file in the subagents folder. Inside each group, keep per-model sums.
- Images = items with `type == "image"` inside `tool_result` content lists of `type == "user"` lines, counted per group.
- Window: only lines with `timestamp` (ISO 8601, `Z`) strictly after `since` and up to the end. `until` = the largest timestamp counted (lead group), or the `since` value when nothing new was counted.

## 4. Commands

Every command: exit 0 on success, 2 on a usage or validation error (message on stderr, one line per problem, with the fix). No traceback unless `--debug`.

### `start` (SessionStart hook)
Reads hook JSON from stdin as UTF-8 bytes (not the console code page; empty or invalid → treat as `{}`, print lines 1–2 only). Never fails: any exception → print nothing, exit 0. Must finish in < 2 s on a 50 MB transcript folder (do not read files larger than 50 MB). `auto` = `off` or `keywords` → print nothing. Otherwise print at most 5 lines, each ≤ 220 chars:
1. Always: `lean-team <VERSION> is installed. For multi-step work (builds, research, refactors, anything you would delegate) load the lean-team skill first; do small fixes yourself.`
2. Always: `Tool: bash "<abs path of lt.sh>" status | tokens | log` (own line, so a long install path is never cut).
3. If the project layer exists: `Project layer: <path> (<n> lines) — read it after loading the skill.`
4. If consolidation is due (§4 `status`): `Learning: <k> iterations since the last consolidation — consolidate first (lt.sh status).`
5. If the newest other transcript in the same transcripts folder as `transcript_path` (by mtime, size ≤ 50 MB) used the skill — it contains a `Skill` tool call whose `skill` contains `lean-team`, or a user line containing `<command-name>/lean-team` — and `metrics.jsonl` has no line with that `session`, and `DATA/sessions/<id>.nudged` does not exist: `Last session <first 8 chars> used lean-team but logged no metrics: bash "<lt.sh>" log --session <id> ... (or ignore).` Then create the `.nudged` marker.

### `prompt` (UserPromptSubmit hook)
Reads hook JSON from stdin; never fails (exception → nothing, exit 0). Print nothing when `auto` = `off`, when the prompt contains `/lean-team`, or when `DATA/sessions/<session_id>.hinted` exists. Otherwise, if the prompt matches a keyword (case-insensitive, Unicode-aware: `lean-team`, `lean team`, `эконом`, `токен`, `дешёв`, `дешев`, `save tokens`, `fewer tokens`, `cheap`, `token budget`), print exactly one line `lean-team: the user wants to save tokens — load the lean-team skill before planning, if it is not loaded yet.` and create the `.hinted` marker.

### `tokens [--session ID] [--since ISO | --since-last-log] [--json]`
`--since-last-log`: `since` = `until` of the last `metrics.jsonl` line whose `session` is this session (none → no lower bound). Text output ≤ 10 lines: one header line with the session (8 chars) and window, one line per group × model: `group model calls=N in=… write=… read=… out=… effective=…` (numbers as `123`, `45.6k`, `1.23M`), a total line, an images line. `--json` prints the object written to `tokens` in §5 plus `until`. Transcript not found → exit 2: `transcript for session <id> not found under <root>`.

### `log` — append one metrics line (schema §5)
Arguments: `--task` (required, ≤ 80 chars), `--kind` (required: `build|fix|review|research|content|media|plan|ops`), `--success` (required: `yes|partial|no`), `--rules` (comma list, default none), `--new` (comma list), `--review-rounds` (int ≥ 0, default 0), `--causes` (comma list from: `brief-ambiguous, design-not-decided, ownership-too-narrow, brief-contradictory, scope-grew-in-review, executor-weak, executor-blocked, env-tooling, flaky-test, lead-error, user-correction`), `--user-corrections` (int ≥ 0, default 0), `--external` (comma list `executor:model=tokens`, e.g. `codex:gpt-6.1-sol=216000`), `--limits` (comma list `week=+3,5h=+12`, percentage points, Claude plan), `--note` (≤ 160 chars), `--session`, `--project`, `--project-dir`, `--dry-run` (print the line, write nothing).
Validation (all problems reported at once, nothing written):
- every `--rules` id must be known: a candidate id in `candidates.md` (any heading `## <id>` where id is the first token, trailing `:` stripped), or an id written anywhere in `local.md` or the project layer. Ids look like `C-2026-10-25-a`, `C-2026-10-22-cos4`, `C12`.
- every `--new` id must be a candidate id in `candidates.md` (candidates are written before the next task).
- unknown causes, bad ints, over-long text → error.
Tokens = §3 with `--since-last-log` semantics; transcript not found → write `"tokens": null` and warn on stderr (still exit 0). After writing, print the line's short summary (≤ 2 lines) and the `status` summary.

### `status [--project NAME] [--open] [--json]`
- Iterations since consolidation = number of non-empty lines in `metrics.jsonl` after line `state.json.consolidated_at_line` (default 0; legacy lines count). Due when ≥ 5.
- Candidates are parsed from `candidates.md` (strict format §6). Headings `## C…` not in the strict format count as `unformatted`.
- For each strict candidate with status `candidate` or `trial`: `yes` = evidence lines with `effect=yes`, `total` = evidence lines, `worse` = any `quality=worse`. **Ready**: not worse and (mechanical: yes ≥ 1; large: yes ≥ 2; small: total ≥ 3 and yes ≥ 2). **Retire**: total ≥ 5 and yes = 0. **Check**: worse. Also `applied` = number of v1 metric lines listing the id in `rules_applied`.
- Size caps: personal layer > 60 lines, project layer > 40 lines → over the cap.
- Default text output ≤ 8 lines: header with project; iterations since consolidation (+ `consolidate now` when due); counts (strict, unformatted, open for this project); `ready:` up to 5 ids with type and yes/total, then `+N`; `retire:`; `check:`; caps.
- `--open`: instead, list open strict candidates (status candidate/trial) whose scope is `core`, `personal` or `project:<this project>`, one line each, ≤ 20 lines: `<id> · <type> · <status> · <yes>/<total> · <action, first 90 chars>`.

### `consolidated`
Write `state.json` `{"consolidated_at_line": <current non-empty line count of metrics.jsonl>, "date": "<YYYY-MM-DD>"}`; print one line.

### `config [--auto remind|keywords|off]`
Without arguments print the current value; with `--auto` write `config.json` (keep other keys).

## 5. Metrics line, schema v1

One JSON object per line, keys in this order, nothing else:
```json
{"v": 1, "date": "2026-10-25", "until": "2026-10-25T14:02:11.120Z", "session": "<id>", "project": "COS", "skill_version": "2.2.0",
 "task": "...", "kind": "build", "success": "yes", "review_rounds": 1, "causes": [], "user_corrections": 0,
 "rules_applied": ["C-2026-10-20-b"], "candidates_new": [],
 "tokens": {"lead": {"calls": 45, "input": 900, "write_5m": 0, "write_1h": 410000, "read": 9100000, "output": 61000, "effective": 2035900, "images": 2,
                     "models": {"claude-opus-5-5": {"calls": 45, "input": 900, "write_5m": 0, "write_1h": 410000, "read": 9100000, "output": 61000, "effective": 2035900}}},
            "subagents": {"calls": 0, "input": 0, "write_5m": 0, "write_1h": 0, "read": 0, "output": 0, "effective": 0, "images": 0, "models": {}},
            "external": {"codex:gpt-6.1-sol": 216000}},
 "limits": {"week": 3, "5h": 12}, "note": "..."}
```
Readers must accept legacy lines (no `"v"`): use only `date`, `project`, `session` (if any) and `rules_applied` (ignore non-list values).

## 6. Candidate format (strict)

```markdown
## C-2026-10-25-a · mechanical · candidate · project:COS
Action: before a render, run one verify script that prints ≤ 20 lines
Metric: tool calls per build 80 → ≤ 60 (written 2026-10-25, before the first application)
- 2026-10-26 COS/short8 v2.2.0: effect=yes, tool calls 80 → 52, quality=same
```
- Heading regex: `^## (C-\d{4}-\d{2}-\d{2}-[a-z0-9]+|C\d+) · (mechanical|large|small) · (candidate|trial|rule|proposed-to-core|retired) · (core|personal|project:\S+|adapter:\S+|recipe:\S+)\s*$`
- `Action:` = the first line starting with `Action:` before the next heading.
- Evidence line regex: `^- (\d{4}-\d{2}-\d{2}) (\S+) v([\d.]+): (.*)$`; inside, `effect=(yes|no)` and `quality=(same|better|worse)` (missing quality = same; missing effect → the line is not evidence).

## 7. Tests the suite must cover

tokens: duplicates by `message.id` counted once; 5m/1h split and the fallback; effective formula; `<synthetic>` skipped; sidechain lines and subagent files go to `subagents`; images per group; `--since` window and `until`; `--since-last-log` after a `log`. log: missing required args; unknown cause; unknown rule id; id accepted from the project layer and from `local.md`; `--new` must be in candidates; `--dry-run` writes nothing; written line has exactly the §5 keys in order; external and limits parsing; transcript missing → `tokens: null`, exit 0. status: due at 5 lines and reset by `consolidated`; thresholds for each type (mechanical 1 yes ready; large 1 not, 2 ready; small 3 lines with 2 yes ready, 2 lines not); retire at 5 no; worse → check; unformatted count; caps; `--open` scope filter and line limit; legacy lines tolerated. start: ≤ 5 lines; `off`/`keywords` → nothing; layer line; due line; nudge once for a previous session that used the skill without a metrics line; invalid stdin → exit 0 and no output beyond line 1. prompt: Russian and English keywords; once per session; `/lean-team` and `off` → nothing; invalid stdin → nothing. config set/get. VERSION equals plugin.json.
