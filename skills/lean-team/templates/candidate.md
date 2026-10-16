# Candidate entry format (`~/.claude/lean-team/candidates.md`)

```markdown
## C<n>: <the rule as an action>
- Scope: core | personal | project:<name> | adapter:<name> | recipe:<name>
- Expected effect: <metric> should <rise|fall> (e.g. review rounds per step ≤ 2)
- Status: candidate | trial | rule | proposed-to-core | retired
- Evidence (one line per application):
  - <date> <project/step>: applied=<yes|no>, <metric before → after>, quality <same|better|worse>, note
```

Promote, retire and consolidate by the thresholds in SKILL.md §8. One success is a trial, not a rule.
