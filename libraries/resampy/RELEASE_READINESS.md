# resampy v0.1.0 — Release Readiness

Assessment of the native Mojo port of the supported `resampy` 0.4.3
`resample` contract for a first public release. This document records evidence
and open items; it does not itself create a tag or release.

**Base:** branch `main`, HEAD `7e7784a`
(`feat(resampy): add reproducible performance benchmarks`).

## 1. Decision summary

| Item | Status |
|---|---|
| Implementation | Complete for the v0.1.0 scope |
| Numerical parity | Complete for the tested 1-D Float64 integer-rate contract |
| Benchmarks | Complete; 275/275 exact gates PASS |
| Test suite | Complete; 144 native + 90 Python tests |
| Documentation | Release documents and status updates complete |
| Production coefficient redistribution | **Unresolved** |
| **Verdict** | **BLOCKED** |

A release must not be published while a mandatory production resource remains
unlicensed for redistribution. The repository does not include or regenerate
the production coefficient table.

## 2. Implemented surface

- 1-D Float64 whole-buffer `resample`, integer sampling rates, integer or
  non-integer rate ratios.
- `output_length` with upstream truncating semantics.
- Band-limited windowed-sinc interpolation with `scale = min(1, ratio)`,
  first-order half-window interpolation, forward-difference table,
  zero-extension boundaries, and downsampling gain compensation.
- Equal-rate exact copy and empty/zero-length success path.
- Validated two-file filter resource: JSON metadata plus little-endian Float64
  payload with SHA-256 integrity checking.
- Framed CLI: `OP_PING`, `OP_ECHO`, representation/verification opcodes
  `0x20`–`0x29`, and `OP_RESAMPLE = 0x2A`.
- Synthetic coefficient resource only (`synthetic_tiny_v1`, 8 coefficients).

Deferred: `kaiser_best`, `resample_nu`, N-D/arbitrary `axis`, float32,
complex, integer-to-float conversion, `parallel`, runtime filter generation,
callable filters, non-integer sampling rates, and Python-to-Mojo interop.

## 3. Compatibility scope and deviations

Supported claim: 1-D Float64, integer rates, `kaiser_fast` supplied as a
validated resource, sequential execution with `--fp-mode contract=off`.

Accepted deviations:

- Empty input or a result truncating to zero returns an empty buffer; upstream
  raises `ValueError`.
- Rates are integers only; upstream accepts non-integer rates.
- Output is capped at 1,000,000 samples.
- Filter precision must be in `[1, 1,000,000]`, must not exceed a non-empty
  coefficient count, and all filter coefficients must be finite.
- Mojo raises `Error`; the CLI returns `STATUS_ERROR`. Python exception types
  and message text are not reproduced.
- CLIs enforce the 64 MiB frame and 16 MiB response limits; compute cost is not
  separately time-bounded.

## 4. Numerical evidence

- 19 committed upstream parity tests: 15 finite signal/rate cases and 4
  non-finite/subnormal cases. Every finite output was bit-identical
  (`atol = rtol = 0`); non-finite outputs matched position-wise.
- Extended finite sweep: 1,684 signal/rate combinations, zero bit mismatches.
- All 17 committed resampling golden vectors use the independent stdlib
  reference and synthetic coefficients; the drift check compares regenerated
  content.
- Upstream table used for parity:
  `kaiser_fast_upstream_0_4_3`, 12,289 coefficients, precision 512, rolloff
  `0.8682120388377784`, SHA-256
  `4c96a90d1b0b93cf0a9620c5f66216416a6b19752bf18a208c837b55b719434b`.
- The upstream table is written to a temporary directory at test time and is
  never committed.

## 5. Test inventory

| Suite | Count | Result |
|---|---:|---|
| Native Mojo test functions | 144 | Pass |
| Python compatibility tests | 90 | Pass |
| Upstream parity subset | 19 | Pass |
| Resampling golden vectors | 17 | Drift check pass |
| Representation golden vectors | 12 | Drift check pass |
| Benchmark correctness cells | 275 | 275 PASS, 0 FAIL |

Native suites: `test_signal` (13), `test_output` (10), `test_float_codec`
(18), `test_json_codec` (21), `test_coefficients` (19),
`test_numerical_compare` (21), `test_golden_vector` (16), `test_cli` (3), and
`test_resample` (23).

Repository-wide `scripts/run_all_tests.py` passed: **442 native tests** across
39 suites, **771 Python tests**, `ruff check`, `ruff format --check`, and all
five library vector drift checks.

## 6. Benchmark evidence

Artifacts were regenerated from clean HEAD `7e7784a`; the report records
`dirty=False`.

- 275 measured cells, 5 documented exclusions.
- 2 independent runs, 5 warmups, 25 samples per path.
- Median-of-medians aggregation; seed `20260610`.
- Paths: upstream warm, upstream cold (fresh-process JIT), native in-process,
  native CLI.
- Exact SHA-256 gate: 275/275 PASS; max absolute error 0.0, RMSE 0.0.
- Native in-process vs upstream warm: `0.13x–0.25x` across rate-pair
  aggregates (upstream faster on this host).
- CLI overhead: `15x–33x` native in-process; 1:1 is process-floor dominated.
- Cold costs: upstream first call `455.025 ms`; native bench build
  `1634.096 ms`; native CLI build `1983.624 ms`; CLI ping floor
  `16.727 ms`.
- Python-to-Mojo interop is unavailable and reported as a gap.
- No optimization work was performed and no universal-speedup claim is made.

Evidence:
[`benchmarks/reports/BENCHMARK_REPORT.md`](benchmarks/reports/BENCHMARK_REPORT.md),
`benchmarks/results/raw_results.json`,
`benchmarks/results/summary.csv`,
`benchmarks/results/environment.json`.

## 7. Toolchain and reproducibility

- Mojo 1.2.0 (`2016d0cd`) via `.venv/bin/mojo`; numerical builds and tests use
  `--fp-mode contract=off`.
- Host Python 3.13.14.
- Pinned reference: resampy 0.4.3 at
  `7c484f8eec54b87e8f566578dc3e48a2be81cc80`; NumPy 2.5.5; Numba 0.68.1;
  llvmlite 0.50.0.
- Benchmark host: AMD Ryzen 7 6800H, 16 logical cores, affinity CPU 0,
  15,528,948 kB RAM, Linux 7.0.0-28-generic.
- Repository-wide regression entry point:
  `.venv/bin/python scripts/run_all_tests.py`.
- Vector drift check:
  `.venv/bin/python libraries/resampy/tests/vectors/generate_resample_vectors.py --check`.

## 8. Licensing and provenance gate — BLOCKING

Facts:

- Upstream `resampy` 0.4.3 is ISC-licensed; the copyright and permission
  notice is retained in `THIRD_PARTY_NOTICES.md`.
- The native implementation is independent; upstream source is not vendored.
- The production `kaiser_fast` table is upstream numeric data. Its
  redistribution status is unresolved. The ISC license is **not assumed** to
  settle the coefficient-table question.
- The repository contains only the synthetic 8-coefficient resource. Tests and
  benchmarks derive the production table from the installed package into a
  temporary directory and delete it.
- The Phase 1 licensing audit's questions Q1–Q6 remain unresolved; see
  [`docs/licensing-audit.md`](docs/licensing-audit.md) §6.

**Exact outstanding requirement:** obtain written clearance from the rights
holder (or an authorized reviewer) permitting redistribution of the
`resampy` 0.4.3 `kaiser_fast` coefficient table under stated terms, or provide
an alternative production filter resource whose redistribution terms are
explicitly documented and compatible. Record the decision, required notice
text, and resource provenance/integrity metadata in the licensing audit and
`THIRD_PARTY_NOTICES.md` before including the resource.

Until then: do not commit, embed, package, or distribute the production table;
do not describe the release as ready or published.

## 9. Documentation and repository integration

- Library README updated from the stale Phase 5 status to v0.1.0 release
  candidate status, benchmark evidence, and the licensing blocker.
- New `CHANGELOG.md`, `RELEASE_NOTES_v0.1.0.md`, and this readiness report.
- Root README, roadmap, and third-party notices updated to reflect Resampy's
  implementation/benchmark status and the unresolved coefficient-data issue.
- `resampling-design.md` corrected the recorded rolloff value and replaced the
  stale "benchmarking deferred" statement with Phase 6 evidence.
- `licensing-audit.md` records the Phase 7 release gate.
- No implementation arithmetic, tests, vectors, benchmark methodology, or
  coefficient data were changed.

## 10. Recommended version

**v0.1.0** — first public implementation of the restricted `resample`
contract. It is not a drop-in replacement for the full Resampy Python API, and
it is not yet publishable.

## 11. Release blockers

1. **Production coefficient redistribution clearance** (§8). This is the sole
   mandatory blocker.
2. No tag, package, or release may be created while blocker 1 remains open.

Non-blocking follow-ups: optimize native per-call overhead and allocation if
performance becomes a goal; evaluate Python-to-Mojo interop; add `kaiser_best`,
multi-channel, and additional dtypes in later versions; re-run benchmarks on a
quiet host before publishing tighter performance claims.

## 12. Verdict

**BLOCKED**

The implementation, parity evidence, tests, and benchmarks meet the v0.1.0
technical bar. Release is blocked solely because the mandatory production
`kaiser_fast` coefficient resource has not been cleared for redistribution.
The exact outstanding requirement is stated in §8.

No commit, push, tag, GitHub release, package publication, or coefficient
redistribution was performed as part of this assessment.
