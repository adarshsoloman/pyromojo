# resampy v0.1.0 — Release Handoff

**Status: BLOCKED — LICENSING**

- Handoff date: 2026-11-20
- Repository: PyroMojo
- Handoff base: `5c20c8a` (`docs(resampy): prepare v0.1.0 release readiness`)
- Handoff first committed: `fc765e6` (`chore(resampy): finalize Phase 8 release handoff`)
- Working tree at handoff: clean; no tracked release artifact or uncommitted change
- Release performed: **No**
- Tag created: **No** (`resampy-v0.1.0` does not exist)
- Package published: **No**
- GitHub release created: **No**

This handoff records the state of the v0.1.0 work for a future maintainer. It
was integrated during repository finalization and does not approve or perform a
release.

## 1. Final technical status

The implementation, parity verification, and benchmarks meet the stated
v0.1.0 technical bar for the restricted contract:

- 1-D Float64 whole-buffer resampling.
- Integer sampling rates, including non-integer ratios between integer rates.
- Externally supplied, validated `kaiser_fast`-format filter resource.
- Sequential Float64 execution built with `--fp-mode contract=off`.

Verification at the handoff base:

| Check | Result |
|---|---|
| Full repository regression (`scripts/run_all_tests.py`) | Pass |
| Native Mojo tests | 442 passed across 39 suites |
| Python tests | 771 passed |
| Resampy native tests | 144 across 9 suites |
| Resampy Python compatibility tests | 90 |
| Committed upstream parity tests | 19 passed |
| Extended finite parity sweep | 1,684 cases, zero bit mismatches |
| Repository drift checks | 5 passed, including 17 resampling and 12 representation vectors |
| Benchmark correctness gate | 275/275 exact SHA-256 matches |
| Benchmark exclusions | 5 documented |
| `ruff check` / `ruff format --check` | Pass |

The benchmark artifacts were generated at source revision `7e7784a`
(`dirty=False`) and committed in the documentation commit `5c20c8a`. No
implementation, test, or benchmark-methodology change occurred after
`7e7784a`.

Toolchain: Mojo 1.2.0 (`2016d0cd`), Python 3.13.14, upstream `resampy==0.4.3`
at commit `7c484f8eec54b87e8f566578dc3e48a2be81cc80`, NumPy 2.5.5,
Numba 0.68.1, llvmlite 0.50.0.

## 2. Supported API

- `resample(signal, sr_orig, sr_new, filter) -> OutputBuffer`
  - `signal`: 1-D Float64 values.
  - `sr_orig`, `sr_new`: positive integer sampling rates.
  - `filter`: validated `FilterCoefficients` resource.
- `output_length(input_length, sr_orig, sr_new) -> Int`
  - Upstream truncating rule: `int(L * float(sr_new) / float(sr_orig))`.
- Native CLI:
  - Representation/verification opcodes `0x20`–`0x29`.
  - `OP_RESAMPLE = 0x2A`.
  - Length-framed requests; malformed input yields `STATUS_ERROR`.

Input limits and validation:

- Output capped at 1,000,000 samples.
- Filter precision in `[1, 1,000,000]`; precision must not exceed a non-empty
  coefficient count.
- Coefficients must be finite.
- Filter resource is a strict JSON + little-endian Float64 pair with SHA-256
  verification and bounded reads.
- CLI frame limit is 64 MiB; response limit is 16 MiB.

Documented deviations:

- Empty input or output truncating to zero returns an empty buffer; upstream
  raises `ValueError`.
- Non-integer sampling rates are out of scope.
- Error types are Mojo `Error` / CLI `STATUS_ERROR`, not Python exception
  classes.
- No Python-to-Mojo runtime interop.

Deferred: `kaiser_best`, `resample_nu`, N-D/arbitrary `axis`, float32,
complex, integer-to-float conversion, `parallel`, runtime filter generation,
callable filters, and performance optimization.

## 3. Test and parity evidence

Primary commands:

```bash
.venv/bin/python scripts/run_all_tests.py
.venv/bin/python libraries/resampy/tests/run_phase3_tests.py
.venv/bin/pytest -q libraries/resampy/tests/python_compat/test_upstream_parity.py
.venv/bin/python libraries/resampy/tests/vectors/generate_resample_vectors.py --check
```

Parity reference:

- `resampy` 0.4.3, commit
  `7c484f8eec54b87e8f566578dc3e48a2be81cc80`, ISC.
- Finite outputs were bit-identical (`atol = rtol = 0`).
- Non-finite outputs matched position-wise.
- The upstream parity tests derive `kaiser_fast` from the installed package
  into a temporary directory and delete it.

## 4. Benchmark baseline

- Paths: upstream warm, upstream cold (fresh-process JIT), native in-process,
  native CLI.
- 275 measured cells; 5 documented exclusions for zero-length output cases.
- 2 independent runs, 5 warmups, 25 samples per path, median-of-medians,
  seed `20260610`.
- Exact correctness gate: 275/275 PASS; maximum absolute error 0.0; RMSE 0.0.
- Native in-process vs upstream warm: `0.13x–0.25x` across rate-pair
  aggregates; upstream is faster on the recorded host.
- Native CLI overhead: `15x–33x` native in-process, except 1:1, which is
  dominated by the `~16.7 ms` process floor.
- Cold costs: upstream first call `~455 ms`; native bench build `~1.63 s`;
  native CLI build `~1.98 s`.
- Host: AMD Ryzen 7 6800H, 16 logical cores, affinity CPU 0, 15,528,948 kB
  RAM, Linux 7.0.0-28-generic.
- No optimization work was performed and no universal-speedup claim is made.
- The full 275-cell benchmark was not rerun during the Phase 8 audit; the
  existing artifacts and `run_benchmarks.py --self-check` were inspected
  instead to avoid altering recorded results.

Artifacts:

- `benchmarks/reports/BENCHMARK_REPORT.md`
- `benchmarks/results/raw_results.json`
- `benchmarks/results/summary.csv`
- `benchmarks/results/environment.json`

## 5. Licensing blocker

The release is blocked by one mandatory item: the production `kaiser_fast`
coefficient table is not cleared for redistribution.

Verified facts:

- Upstream `resampy` 0.4.3 is ISC-licensed; its notice is retained in
  `THIRD_PARTY_NOTICES.md`.
- The native implementation is independent; upstream source is not vendored.
- The production table is upstream numeric data. Its redistribution status is
  unresolved; the ISC license is not assumed to settle the data-file question.
- No written clearance or alternative licensed production filter resource is
  present in the repository.
- The repository commits only `synthetic_tiny_v1`: 8 coefficients, 64 bytes,
  SHA-256
  `ea129349b224e27e681fe60953110ed888c359fcb10f6d44a6859cf378be952e`.
- The production table is absent: `kaiser_fast_upstream_0_4_3`, 12,289
  coefficients, precision 512, rolloff `0.8682120388377784`, SHA-256
  `4c96a90d1b0b93cf0a9620c5f66216416a6b19752bf18a208c837b55b719434b`.
- Parity tests and benchmarks derive the production table at runtime into a
  temporary directory and delete it.

Exact action to unblock:

1. Obtain written clearance from the rights holder or an authorized reviewer
   permitting redistribution of the `resampy` 0.4.3 `kaiser_fast` table under
   stated terms, **or** provide an alternative production filter resource
   whose redistribution terms are explicitly documented and compatible.
2. Record the decision, required notice text, provenance, and resource
   integrity metadata in `docs/licensing-audit.md` and
   `THIRD_PARTY_NOTICES.md`.
3. If an alternative resource is used, record it as a new resource with its
   own `filter_id`, precision, rolloff, byte order, size, and SHA-256.
4. Re-run the exact parity and benchmark gates against that resource.
5. Update the release readiness verdict only after the evidence is committed.

Until then: do not commit, embed, package, or distribute the production table;
do not create a tag, package, or GitHub release; do not describe the release as
ready or published.

## 6. Remaining known limitations

- Release blocked on coefficient licensing; only a synthetic resource ships.
- Integer sampling rates only; non-integer rates are unsupported.
- Empty or zero-length output succeeds with an empty buffer, unlike upstream.
- Output capped at 1,000,000 samples.
- Filter precision and finite-coefficient validation are stricter than
  upstream.
- Mojo/CLI error behavior does not reproduce Python exception types/messages.
- No Python-to-Mojo interop; reported as a benchmark gap.
- Deferred algorithm and data-shape features listed in §2.
- CLI compute cost has no runtime budget beyond frame/response/size limits.
- Benchmark results are host- and toolchain-specific; no universal speedup
  claim is made.

## 7. Release decision

**BLOCKED — LICENSING.**

The technical release bar is met. The sole mandatory blocker is production
coefficient redistribution clearance. No release action was taken, and no
release is approved by this handoff.
