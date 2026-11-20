# Resampy v0.1.0 — release notes draft

> **Release status: BLOCKED — LICENSING.** The native
> implementation, numerical verification, and benchmarks are complete, but
> written clearance to redistribute the production `kaiser_fast` coefficient
> table has not been obtained. See [Release readiness](RELEASE_READINESS.md)
> §8 and [licensing audit](docs/licensing-audit.md) §6. This draft does not
> claim that a tag or release exists.

Native Mojo port of the supported `resampy` 0.4.3 `resample` contract:
1-D Float64, integer sampling rates, and a validated external `kaiser_fast`
filter resource.

## What the implementation includes

- **`resample` and `output_length`** for whole-buffer 1-D Float64 signals.
- **Integer sampling rates** with integer or non-integer rate ratios
  (for example `44100 -> 48000`).
- **Windowed-sinc kernel** matching upstream length, phase, boundary,
  downsampling-gain, and accumulation order, built with
  `--fp-mode contract=off`.
- **Native framed CLI** with `OP_RESAMPLE = 0x2A` and representation /
  verification opcodes `0x20`–`0x29`.
- **Validated filter resource format** (JSON metadata + little-endian Float64
  payload, SHA-256 checked). A synthetic resource is committed; production
  coefficients are supplied by the caller.
- **Golden vectors and drift checks** — 17 resampling cases from the
  independent stdlib reference and 12 representation cases.
- **Four-path benchmark suite** — upstream warm, upstream cold, native
  in-process, and native CLI over 275 measured cells.

## Correctness evidence

- **Reference:** resampy **0.4.3** at commit
  `7c484f8eec54b87e8f566578dc3e48a2be81cc80`, ISC; NumPy 2.5.5,
  Numba 0.68.1, llvmlite 0.50.0.
- **Native tests:** 144 test functions across 9 suites, all passing.
- **Python tests:** 90 compatibility tests, all passing.
- **Upstream parity:** 19 committed tests (15 finite signal/rate cases plus
  4 non-finite/subnormal cases). Finite outputs were **bit-identical**;
  non-finite outputs matched position-wise.
- **Extended sweep:** 1,684 finite signal/rate combinations, zero bit
  mismatches.
- **Benchmark gate:** **275/275 cells PASS** by exact SHA-256 equality of the
  little-endian Float64 output. Output lengths also matched exactly.

The upstream parity tests and benchmark derive the production coefficient
resource from the installed package into a temporary directory and delete it.
No upstream coefficient table is committed.

## Benchmark results

Measured on an AMD Ryzen 7 6800H, Linux, Mojo 1.2.0, single pinned CPU;
2 runs, 5 warmups, 25 samples per path, median-of-medians.

- **Native in-process vs upstream warm:** `0.13x–0.25x` across rate-pair
  aggregates. Upstream warm is faster on this host; 1:1 is allocation-floor
  dominated.
- **Native CLI overhead:** `15x–33x` native in-process, except 1:1, which is
  dominated by the `~16.7 ms` process floor.
- **Cold costs, reported separately:** upstream first call `~455 ms`
  (Numba JIT + execution); native bench build `~1.63 s`; native CLI build
  `~1.98 s`.
- **No universal-speedup claim.** No optimization work was performed.

Full tables and raw data:
[`benchmarks/reports/BENCHMARK_REPORT.md`](benchmarks/reports/BENCHMARK_REPORT.md),
`benchmarks/results/raw_results.json`, `benchmarks/results/summary.csv`,
`benchmarks/results/environment.json`.

## Known limitations and deviations

- **Release blocked:** production `kaiser_fast` coefficient redistribution is
  unresolved. The repository commits only a synthetic filter.
- **Integer sampling rates only.** Non-integer rate ratios from integer rates
  are supported; non-integer rates are not.
- **Empty output:** empty input or a result that truncates to zero returns an
  empty buffer. Upstream raises `ValueError`; callers needing that exception
  must check `output_length` first.
- **Output cap:** results above 1,000,000 samples are rejected before
  allocation.
- **Deferred:** `kaiser_best`, `resample_nu`, N-D/arbitrary `axis`, float32,
  complex, integer-to-float conversion, `parallel`, runtime filter generation,
  callable filters, and Python-to-Mojo interop.
- **CLI limits:** metadata is bounded by the 64 MiB frame limit, and compute
  cost is bounded only by the documented input/filter/output limits; there is
  no runtime budget or timeout.
- **Benchmark scope:** single host, single core, shared-machine noise. Numbers
  are specific to the recorded environment and toolchain.

## Requirements

- **Mojo 1.2.0** via `uv` (`.venv/bin/mojo`); numerical builds must use
  `--fp-mode contract=off`.
- **Python ≥ 3.11** for the host.
- Pinned upstream reference for parity and benchmark: `resampy==0.4.3`,
  `numpy==2.5.5`, `numba==0.68.1`, `llvmlite==0.50.0`.

Quick verification:

```bash
uv sync --extra dev
.venv/bin/python scripts/run_all_tests.py
.venv/bin/python libraries/resampy/tests/vectors/generate_resample_vectors.py --check
.venv/bin/python libraries/resampy/benchmarks/run_benchmarks.py
```

## Links

- [Resampy README](README.md) · [API scope](docs/api-scope.md)
- [Resampling design](docs/resampling-design.md) · [Reference audit](docs/reference-audit.md)
- [Licensing audit](docs/licensing-audit.md) · [Benchmark design](docs/benchmark-design.md)
- [Benchmark report](benchmarks/reports/BENCHMARK_REPORT.md)
- [Release readiness](RELEASE_READINESS.md) · [Release handoff](RELEASE_HANDOFF.md)
- [Changelog](CHANGELOG.md)

## Attribution and licensing

The native implementation is independent; upstream source is not vendored. The
reference package is ISC-licensed, and its required notice is retained in
[root `THIRD_PARTY_NOTICES.md`](../../THIRD_PARTY_NOTICES.md). The production
coefficient tables are not included; the only committed coefficient data is
synthetic. Whether redistribution of the production tables requires additional
permission remains unresolved, and no legal conclusion is made here.
Repository license: **Apache-2.0**.
