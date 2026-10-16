# Candidate entry format (`~/.claude/lean-team/candidates.md`)

```markdown
## C<n>: <the rule as an action>
- Scope: core | personal | project:<name> | adapter:<name> | recipe:<name>
- Effect type: mechanical | large | small
- Expected (written <date>, before the first application): <metric> <from> → <to> (e.g. review rounds per step 4 → ≤ 2)
- Status: candidate | trial (<k> of <needed>) | rule | proposed-to-core | retired
- Evidence (one line per application, on real work):
  - <date> <project/step> v<skill version>: applied=<yes|no>, <metric before → after>, quality <same|better|worse>, other candidates applied: <ids|none>
```

Thresholds by effect type: SKILL.md §8. One success is a trial, not a rule.
