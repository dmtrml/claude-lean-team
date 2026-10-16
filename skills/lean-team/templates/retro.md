# Retro after an iteration (≤ 10 lines)

1. **What caused rework?** Name each extra review round or redo and its cause from the list below.
2. **What used the most tokens, and was it necessary?** Biggest agent or step; would a cheaper executor, a smaller context or doing it yourself have reached the same quality?
3. **What would have made the result better at the same or lower cost?** A user correction, a missed check, a weak part of the output.
4. **Which candidate would prevent or improve it?** State it as an action ("before X, do Y"), the metric it should move, the expected value and the effect type. Add or update it in `candidates.md` before the next task, and show it in the iteration report.

Cause list (use these words in metrics and candidates so they can be counted):
`brief-ambiguous` · `design-not-decided` · `ownership-too-narrow` · `brief-contradictory` · `scope-grew-in-review` · `executor-weak` · `executor-blocked` (permissions, limits) · `env-tooling` · `flaky-test` · `lead-error` · `user-correction`.
