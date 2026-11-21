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

## Observed evaluation (2026-11-21)

**Two predeclared new real-package tests succeeded**, one provider GET each and identical zero-network replay. Exact source is <https://api.deps.dev/v3/>; generated graph counts are resolved for a generic 64-bit Linux environment at observation time, not a record of original release-time installed packages.

| Positive case | Observed source facts | Baseline v1 comparison |
| --- | --- | --- |
| npm `axios@1.6.0` | 25 dependency-node instances, 3 distinct direct dependencies, 22 indirect, 37 graph edges. Direct: `follow-redirects@1.16.3`, `form-data@4.0.6`, `proxy-from-env@1.1.0` | V1 M09 download history cannot name these resolved graph edges |
| PyPI `requests@2.31.0` | 4 distinct direct dependencies, 0 indirect, 4 graph edges. Direct: `certifi@2026.10.23`, `charset-normalizer@3.5.2`, `idna@3.20.0`, `urllib3@2.8.0` | V1 M10 downloads do not describe versioned dependency resolution |

**Three negative gates:** unrelated root/version rejected (identified and fixed from first falsification); provider-reported resolution errors remain partial and are not cached as complete (focused tests); no method converts graph counts into users/downloads/revenue or cross-platform market measurements. Every new call returned `observed` and all identical repeats reported `cache_hit=true` and `network_performed=false`.

**Score:** 2/2 positive cases deliver distinct, verifiable source-scoped answers not provided by v1 download metrics; 3/3 negative gates covered by executed focused test bodies/contract. **Utility proof provisionally PASS.** Full product ACCEPT remains withheld pending authentic pytest/full-v1 regression, a maintenance/licensing check, resource profiling on a representative larger package, and a final reviewed merge. The v2 default cache is now separate from v1.
