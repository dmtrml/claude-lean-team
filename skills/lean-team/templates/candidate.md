# Candidate entry format (`~/.claude/lean-team/candidates.md`)

`lt.sh status` counts thresholds from this exact format, so keep the heading and the evidence lines as shown.

```markdown
## C-<date>-<letter> · <mechanical|large|small> · <candidate|trial|rule|proposed-to-core|retired> · <core|personal|project:<name>|adapter:<name>|recipe:<name>>
Action: <the rule as an action: "before X, do Y">
Metric: <metric> <from> → <to> (written <date>, before the first application)
- <date> <project/step> v<skill version>: effect=<yes|no>, <metric before → after>, quality=<same|better|worse>, other candidates applied: <ids|none>
```

Example:

```markdown
## C-2026-10-25-a · mechanical · candidate · project:COS
Action: before a render, run one verify script that prints ≤ 20 lines
Metric: tool calls per build 80 → ≤ 60 (written 2026-10-25, before the first application)
- 2026-10-26 COS/short8 v2.2.0: effect=yes, tool calls 80 → 52, quality=same, other candidates applied: none
```

One evidence line per real application; `effect=yes` only when the target metric moved the expected way. Thresholds by effect type: SKILL.md §8. One success is a trial, not a rule. When a candidate becomes a rule, set its status to `rule` and copy the action (with its evidence count) into the personal or project layer.
