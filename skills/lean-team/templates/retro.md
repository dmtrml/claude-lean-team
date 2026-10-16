# Retro after an iteration (≤ 10 lines)

1. **What caused rework?** Name each extra review round or redo and its cause from the list below.
2. **What used the most tokens, and was it necessary?** Biggest agent or step; would a cheaper executor, a smaller context or doing it yourself have reached the same quality?
3. **Which rule would have prevented it?** State it as an action ("before X, do Y") and the metric it should move. Add or update a candidate (`candidate.md`).

Cause list (use these words in metrics and candidates so they can be counted):
`brief-ambiguous` · `design-not-decided` · `ownership-too-narrow` · `brief-contradictory` · `scope-grew-in-review` · `executor-weak` · `executor-blocked` (permissions, limits) · `env-tooling` · `flaky-test` · `lead-error`.
