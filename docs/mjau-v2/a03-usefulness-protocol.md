# Predeclared five-case usefulness protocol: A03 deps.dev dependency graphs

Recorded 2026-11-21 **before** evaluating these cases. Only legal, free sources. Source-observed facts and uncertainty only; no invented demand measurements. Not approval to merge.

## Cases

1. Positive: npm `axios@1.6.0`. Return resolved direct versioned dependencies and edge counts, source-scoped; v1 package downloads cannot report dependency graph edges.

2. Positive: PyPI `requests@2.31.0`. Return resolved dependencies or honest partial/unavailable when the provider cannot resolve them.

3. Negative: a valid-shaped dependency graph for an unrelated package/version is rejected and never used.

4. Negative: a graph reporting resolution errors remains partial and cannot be stored as complete.

5. Adversarial: a dependency graph does not prove downloads, users, adoption, installed dependents or a standard cross-platform runtime.

## Success gate

At least one newly sampled real package yields valid versioned graph observations; all three negative gates pass; at most two additional live calls.

Record exact response status, primary source link, unit/coverage, real answerability relative to v1, abstentions and failures. A legal, operational, source, or measured-usefulness failure means BLOCK or DISCARD, not quiet retention.
