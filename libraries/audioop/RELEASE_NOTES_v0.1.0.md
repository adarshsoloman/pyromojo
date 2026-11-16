# Audioop v0.1.0

Native Mojo port of CPython 3.12's `audioop` — the legacy audio-sample module removed in Python 3.13.

> This is the first public release of the Audioop port. It is a **correctness release**: every number below passed a three-way exact-equality gate (pure Python == CPython C == Mojo) before any timing was recorded. Performance is reported honestly, including the cases where the C reference wins.

## What is included

- **All 26 public operations** — `add`, `bias`, `mul`, `reverse`, `byteswap`, `lin2lin`, `getsample`, `max`, `minmax`, `avg`, `rms`, `cross`, `avgpp`, `maxpp`, `findmax`, `findfactor`, `findfit`, `tomono`, `tostereo`, `ratecv`, `lin2alaw`, `alaw2lin`, `lin2ulaw`, `ulaw2lin`, `lin2adpcm`, `adpcm2lin` — plus stateful processing for `ratecv` and ADPCM.
- **Widths 1–4** (8/16/24/32-bit), native byte order, `bytes` fragments, reference-compatible sentinels and error messages.
- **Native CLI** and framed binary protocol (`0x22`–`0x3B`, 26 operation opcodes documented in `docs/cli-opcode-registry.md`).
- **G.711** A-law / μ-law and **Intel/DVI ADPCM** codecs (lookup tables transcribed from the reference, SoX `g777.c`/`g771.c` Sun unrestricted-use notice retained in `THIRD_PARTY_NOTICES.md`).

## Complete API coverage

| Module | Operations |
|---|---|
| `samples` | internal layer (widths 1–4, native byte order) |
| `arithmetic` | `add`, `bias`, `mul`, `reverse`, `byteswap`, `lin2lin` |
| `statistics` | `getsample`, `max`, `minmax`, `avg`, `rms`, `cross` |
| `peak_analysis` | `avgpp`, `maxpp`, `findmax`, `findfactor`, `findfit` |
| `channels` | `tomono`, `tostereo` |
| `ratecv` | `ratecv` (stateful) |
| `g711` | `lin2alaw`, `alaw2lin`, `lin2ulaw`, `ulaw2lin` |
| `adpcm` | `lin2adpcm`, `adpcm2lin` (stateful) |

Full 26-operation compatibility matrix: [`PHASE9_RESULTS.md`](PHASE9_RESULTS.md) §4 (all PASS).

## Compatibility and correctness evidence

- **Reference:** CPython **3.12.3** isolated venv (`libraries/audioop/python_reference/.venv`).
- **Native tests:** 8 audioop suites, **105 test functions, all passing**.
- **Python compatibility:** 136 audioop test cases (framing, differential, golden-vector, chunk/state semantics), **681 repo pytest** in total; all passing.
- **Golden vectors:** **1,277 cases** including all 256 A-law and μ-law decoder codewords and all 256 ADPCM byte values; `--check` passes (byte-identical regeneration).
- **Benchmark gates:** **250/250 cells PASS** (pure == C == Mojo, exact bytes/state, no tolerances).

## Benchmark results

Three-way comparison (pure Python vs CPython C vs Mojo, plus CLI path separately) over 250 deterministic workloads (seed `20260610`).

- **Mojo is ~40× pure Python** (per-op 15–110×).
- **Mojo is ~0.26× CPython C** (C typically 2–20× faster; `getsample` is the single exception at ~2.7× Mojo-faster). The gap is dominated by per-call allocation and 64-bit scalar arithmetic; no SIMD work was done — this is a measurement, not a regression to hide.
- **CLI ~16 ms** per request (process spawn) — not a measure of kernel performance.

Full tables: [`benchmarks/reports/BENCHMARK_REPORT.md`](benchmarks/reports/BENCHMARK_REPORT.md) (raw results, summary, and environment metadata under `benchmarks/results/`). Headline numbers are medians-of-medians over 2 runs.

## Known limitations

- `mul`/`tomono`/`tostereo` define NaN results as 0; CPython's `(int)NaN` is undefined (width-4 differs at the byte level; documented, excluded from equality assertions).
- Odd-chunk ADPCM encoder concatenation is not byte-equal to whole encoding (CPython behaviour, documented).
- Big-endian I/O, the buffer protocol / NumPy inputs, and batch SIMD variants are out of scope for v0.1.0.
- Absolute benchmark numbers carry shared-machine noise (taskset-pinned to cores 11/13, no frequency locking); medians-of-medians mitigate but do not eliminate it.

## Requirements

- **Mojo 1.2.0** via `uv` (`.venv/bin/mojo`); system Mojo 1.0.0 is unsupported.
- **Python ≥ 3.11** for the host; isolated **CPython 3.12.3** for the reference.
- `uv sync --extra dev` provisions the toolchain.

Quick verification:

```bash
uv sync --extra dev
.venv/bin/python scripts/run_all_tests.py
libraries/audioop/python_reference/.venv/bin/python \
  libraries/audioop/python_reference/generate_audioop_vectors.py --check
```

Benchmarks:

```bash
.venv/bin/python libraries/audioop/benchmarks/run_benchmarks.py --runs 2
# summary + report only (no re-measure)
.venv/bin/python libraries/audioop/benchmarks/run_benchmarks.py --report-only
```

## Links

- [Audioop README](README.md) · [API scope](docs/api-scope.md) · [Sample representation](docs/sample-representation.md)
- [Arithmetic](docs/arithmetic-operations.md) · [Statistics](docs/statistics-operations.md) · [Peak analysis](docs/peak-analysis.md) · [Channel ops](docs/channel-operations.md) · [Ratecv](docs/ratecv.md) · [G.711](docs/g711.md) · [ADPCM](docs/adpcm.md)
- [Benchmark design](docs/benchmark-design.md) · [Benchmark report](benchmarks/reports/BENCHMARK_REPORT.md) · [CLI opcode registry](docs/cli-opcode-registry.md)
- [Release readiness](RELEASE_READINESS.md) · [Changelog](CHANGELOG.md) · [CPython reference audit](docs/reference-audit.md)
- Root: [LICENSE](../../LICENSE) · [THIRD_PARTY_NOTICES.md](../../THIRD_PARTY_NOTICES.md) · [CONTRIBUTING.md](../../CONTRIBUTING.md)

## Attribution and licensing

Independent native implementation — no CPython source was translated. The G.711 and IMA/DVI tables are transcribed from CPython 3.12.3 `Modules/audioop.c` under its embedded Sun Microsystems unrestricted-use notice, recorded in `THIRD_PARTY_NOTICES.md`. Golden vectors are observed outputs (derived data). Repository license: **Apache-2.0**.
