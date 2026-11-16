# Phase 10 Results — Integrated Benchmarking & Release Readiness

Status: **measurement complete; report and release-readiness assessment delivered.**

## 1. Executive summary

All 26 audioop operations were benchmarked through three independently implemented paths — pure-Python floor, CPython 3.12.3 C (ceiling), and native Mojo kernel (in-process `bench.mojo`, 25 samples/cell, 2 runs) — plus a separately measured CLI request path. Every one of the 250 cells passed a three-way exact-equality gate before any timing was recorded.

Headline (median-of-medians, geomean):

- Mojo **~40× faster than pure Python** (per-op 15–110×).
- Mojo **~0.26× CPython C** (C ~4× faster per cell; `getsample` excepted at ~2.7× Mojo-faster). This is a regression relative to C and is reported as such.

## 2. Baseline Git state

- Branch `main`; HEAD `8b7596d docs(audioop): complete compatibility audit` (Phase 9) — working tree was **clean** when Phase 10 began.
- No commits were made during Phase 10; the working tree now contains only Phase 10 additions and two README accuracy fixes.

## 3. Toolchain and hardware environment

- Mojo **1.2.0 (2016d0cd)** via `.venv/bin/mojo`; host Python **3.13.14** (`.venv/bin/python`); reference **CPython 3.12.3** (`libraries/audioop/python_reference/.venv`).
- AMD Ryzen 7 6800H, 16 cores; Linux-7.0.0-28-generic; `time.perf_counter_ns` / `std.time.perf_counter_ns`; seed **20260610**; no frequency locking; benchmark subprocesses pinned with `taskset -c 11,13` to the two least-loaded cores observed at start.
- Cold compile: `bench.mojo` ~1.99 s, `audioop_cli` ~1.85 s (one-time, excluded from all medians).

## 4. Benchmark architecture

- **Pure Python** (`benchmarks/pure_python_reference.py`): per-sample loops reproducing documented CPython algorithms (including 32-bit scaling, `fbound`, band search, IMA/DVI tables). Gated 250/250 exact vs CPython.
- **CPython C**: real `audioop` in the pinned 3.12.3 venv, timed in-process inside a long-lived reference worker (`reference_worker.py`) so no IPC enters the measurement.
- **Native Mojo kernel**: `benchmarks/bench.mojo` builds a text-protocol harness around the real port (`__init__` imports); each workload runs in a fresh process, inputs parsed once outside the timed loop, 5 warmup + 25 measured iterations in-process, sink checksum proves the timed code was not eliminated.
- **CLI path** (labelled, separate): `audioop_cli` per request, 15 samples/cell; `ping` (empty `0x01`) measured 50× as the spawn floor.

## 5. Three-path implementation details

- `workloads.py`: 250 deterministic cells (FNV-1a checksummed); sizes S/M/L = 160/4096/65536 frames; content sweep (silence/square/sine/random/sparse/ramp/clipped/impulses) on 8 representative ops. `write_summary` excludes the 1-Mi tier (pure-Python floor would dominate wall time — documented adaptation).
- `pure_python_reference.py`: all 26 ops (NaN-factor inputs excluded per frozen Phase 0 policy).
- `run_benchmarks.py`: gate (pure==C==Mojo, exact bytes/state) → timed runs (default `--runs 2`) → `results/raw_results.json`, `summary.csv`, `environment.json`, `reports/BENCHMARK_REPORT.md`; `--report-only` regenerates summary+report without re-measuring.

## 6. Workload matrix (250 cells)

- Arithmetic (add/bias/mul/byteswap/reverse × 3 widths × 3 sizes) + stereo `tomono`/`tostereo` at w2.
- Statistics per width (max/minmax/avg/rms/cross/avgpp/maxpp × 3 widths × 3 sizes) + `getsample` first/middle/last on large fragments + `lin2lin` up/down and 4→1.
- Codecs at w2 + w1/w4 spot: `lin2alaw`/`lin2ulaw`/`alaw2lin`/`ulaw2lin` over packed codeword bytes.
- ADPCM cold/warm (`lin2adpcm`/`adpcm2lin`), `ratecv` cold/warm at 8k↔16k and 44.1k→48k (1/2/4 channels, custom and gcd-reduced weights), `find*` windows 1/8/64 with 4× fragments, content sweep on 8 ops.

## 7. Correctness-gate results: 250/250 PASS

Every cell passed a three-way exact gate (bytes; exact `(d, prev, cur)` state for `ratecv`, exact `(valpred, index)` for ADPCM, exact float bytes for `findfactor`/`findfit`) before any timing was recorded. NaN-factor inputs are excluded from benchmarking per policy.

## 8. Full operation-level benchmark results

Full per-cell table (median-of-medians, ns): `benchmarks/reports/BENCHMARK_REPORT.md` §1 (250 rows). Per-operation geometric means (±10% tolerance bands):

| op | cells | mojo/pure | mojo/c | vs pure | vs C |
|---|---:|---:|---:|---|---|
| add | 18 | 31.3x | 0.11x | faster | slower |
| adpcm2lin | 4 | 41.6x | 0.34x | faster | slower |
| alaw2lin | 6 | 17.0x | 0.06x | faster | slower |
| avg | 9 | 37.0x | 0.30x | faster | slower |
| avgpp | 9 | 50.6x | 0.39x | faster | slower |
| bias | 9 | 38.3x | 0.08x | faster | slower |
| byteswap | 9 | 35.3x | 0.22x | faster | slower |
| cross | 17 | 42.4x | 0.27x | faster | slower |
| findfactor | 3 | 27.2x | 0.53x | faster | slower |
| findfit | 3 | 108.4x | 0.77x | faster | slower |
| findmax | 4 | 42.2x | 0.44x | faster | slower |
| getsample | 3 | 17.0x | 2.67x | faster | **faster** |
| lin2adpcm | 12 | 43.5x | 0.42x | faster | slower |
| lin2alaw | 9 | 48.3x | 0.27x | faster | slower |
| lin2lin | 7 | 34.0x | 0.09x | faster | slower |
| lin2ulaw | 17 | 57.0x | 0.34x | faster | slower |
| max | 17 | 39.4x | 0.29x | faster | slower |
| maxpp | 9 | 49.0x | 0.31x | faster | slower |
| minmax | 9 | 36.5x | 0.23x | faster | slower |
| mul | 17 | 45.2x | 0.38x | faster | slower |
| ratecv | 21 | 45.4x | 0.47x | faster | slower |
| reverse | 9 | 36.6x | 0.19x | faster | slower |
| rms | 17 | 37.0x | 0.30x | faster | slower |
| tomono | 3 | 43.3x | 0.29x | faster | slower |
| tostereo | 3 | 44.0x | 0.48x | faster | slower |
| ulaw2lin | 6 | 18.4x | 0.07x | faster | slower |

## 9. Mojo vs pure Python analysis

Geomean **~40× faster** (range 15–110×, median-of-medians across 2 runs). The floor is honest per-sample Python; Mojo's advantage grows slightly with fragment size because per-call overhead dominates both at small sizes. No pathological cells (no Mojo loss vs pure anywhere).

## 10. Mojo vs CPython C analysis

Geomean **~0.26×** (median-of-medians; C ~4× faster overall; per-op 0.03–0.77×, `getsample` excepted at ~2.67×). This is a genuine performance regression relative to the C reference and is reported as such. The gap is smallest where arithmetic dominates per-element work (`findfit` 0.77×, `mul` at large widths ~0.3×) and largest on byte-shuffling inner loops (`lin2lin` 0.09×, `byteswap` ~0.2×) where the C code is a tight pointer loop and the port pays per-sample indexing plus allocation.

## 11. Performance classifications (±10% tolerance around parity)

- **Mojo faster than both**: `getsample` only.
- **Mojo faster than pure Python, slower than C**: all 25 remaining operations.
- **Mojo comparable to C**: none (closest is `findfit` at 0.77×, still below the 0.90 bar).
- **Mojo slower than both**: none.

## 12. Repeated-run stability analysis

Two identical full runs on the shared host; headline numbers are per-cell medians-of-medians (median of the two run medians). Pairwise max-relative-delta: **128/250 within 5%** between run 1 and run 2; all 250 cells have 25 measured samples. The report lists the ten noisiest cells; the pattern is small-workload sensitivity and one environment-sensitive large cell, whose medians nevertheless track the same ordering across runs. No run was cherry-picked; both runs are retained in `raw_results.json`.

## 13. Bottleneck analysis

No optimization was applied (measurement-only). Likely causes, verified by inspection of hot paths:

1. **Allocation per call.** Every op call allocates its result `List` plus one decoded-`Int32` vector per fragment. At 160 frames this dominates (e.g. `max` w2: ~661 ns C vs ~1242 ns Mojo). C allocates a single output buffer.
2. **64-bit scalar arithmetic with per-sample bounds checks.** Port widens to `Int64` and branches per element; C uses native-width pointer increments.
3. **Stateful ops carry per-call vectors** (`RatecvState`, two output lists); no persistent buffers are reused between calls.
4. **CLI path** is process-spawn dominated (~16 ms floor; see §15).

## 14. Compilation and cold-start measurements

- `mojo build bench.mojo`: ~1.99 s (one-time; excluded from medians).
- `mojo build audioop_cli.mojo`: ~1.85 s (one-time; excluded).
- First-request Mojo cold start is not additional beyond the build (no JIT).

## 15. CLI/protocol overhead analysis

Ping (empty `0x01` frame) median ~16.1 ms; mean CLI per-call ~16.0–16.7 ms across all 250 cells. Kernel work (µs scale) is < 1% of any CLI measurement. `cli − ping` approximates kernel + framing at 0.1–0.6 ms for the largest cells. **CLI is a compatibility/test interface, not a performance path.**

## 16. Raw benchmark artifact locations

- `benchmarks/results/raw_results.json` — every sample (25 per cell per run), all runs, full environment metadata.
- `benchmarks/results/summary.csv` — per-cell medians-of-medians with `mojo/pure` and `mojo/c` ratios.
- `benchmarks/results/environment.json` — toolchain/host metadata.
- `benchmarks/reports/BENCHMARK_REPORT.md` — curated tables (regenerable via `--report-only`).

## 17. CLI opcode registry findings

Created `docs/cli-opcode-registry.md`: all 26 operation opcodes `0x22`–`0x3B` verified 1:1 against `protocol.mojo` constants and the `cli.mojo` dispatch (each dispatched exactly once), plus the four infrastructure opcodes. Non-uniformities documented: `findmax` carries no width byte (reference API is fixed 16-bit); decoders impose no fragment-alignment requirement (matching the reference).

## 18. Release-readiness checklist

See `RELEASE_READINESS.md` for the full assessment (26/26 API, 1,277 golden vectors, 105 native audioop tests + 136 compat tests, 641 repo pytest, drift-checked vectors, Sun unrestricted-use notice retained for the transcribed tables, vectors as derived data, no new vendored sources).

## 19. Known deviations and limitations

- NaN-factor inputs excluded from benchmarking per the frozen Phase 0 policy (Mojo defines NaN results as 0; the reference is undefined).
- Width-4 NaN deviation documented (`docs/ratecv.md`, `PHASE6_RESULTS.md`); widths 1–3 match exactly.
- CLI-only representation differences for stateful ops are structural, not semantic.
- 1-MiB tier from the design doc deferred; benchmark corpus is 160/4096/65536.
- Absolute numbers carry shared-machine noise; medians-of-medians mitigate but do not eliminate it.

## 20. Bugs or fixes made

1. Hand-transcribed G.711/ADPCM tables in `pure_python_reference.py` were short (120 of 256 entries): regenerated from the C source.
2. Pure-Python `bias`/`mul`/`lin2lin`/`avg`/`rms`/`tomono`/`tostereo` used 32-bit-scaled samples: fixed to signed samples.
3. Driver `op_args` mismatches for `getsample`/`bias`/`add` and missing wrapper function `_make_pure_fn`: fixed.
4. Driver `canonical_ref` byte-result handling for `add`/`bias` and state-shape handling for `ratecv`: fixed.
5. Benchmark harness `T`-line prefix omitted declared samples; warmup samples included in stats — fixed to declare `T 25 ...` and separate warmup.
6. Per-workload bench processes shared an address space causing sample aliasing; fixed by fresh-process-per-workload and a per-cell sink checksum (exposing the now-fixed `getsample` DCE, which used a trivial 30 ns fast path).
7. Content-sweep table matched primary-matrix cells instead of sweep cells; stability report used first-match instead of index — both fixed.
8. Bench timed-pass redundancies and `else:` fall-through: fixed; `op_args` `_bytes` variants were misrouted (#8).

## 21. Exact validation commands and results

- `.venv/bin/ruff check .` → `All checks passed!` (exit 0)
- `.venv/bin/ruff format --check .` → 146 files already formatted (exit 0)
- `.venv/bin/python scripts/run_all_tests.py` → `all suites passed` — 30 native suites / 298 tests (8 audioop suites = 105 tests); **681 pytest passed**, 0 failed (exit 0)
- `libraries/audioop/python_reference/.venv/bin/python libraries/audioop/python_reference/generate_audioop_vectors.py --check` → `1277 cases match` (exit 0)
- `git diff --check` → clean (exit 0)

## 22. Files changed

Created: `libraries/audioop/benchmarks/` (`bench.mojo`, `pure_python_reference.py`, `reference_worker.py`, `workloads.py`, `run_benchmarks.py`, `README.md`, `results/{raw_results.json, summary.csv, environment.json}`, `reports/BENCHMARK_REPORT.md`), `docs/cli-opcode-registry.md`, `RELEASE_READINESS.md`, `PHASE10_RESULTS.md` (this file).

Modified: repo root `README.md` (audioop status row + stale scope sentences), `libraries/audioop/README.md` (benchmark section + Phase 10 status).

## 23. Final Git status

- Branch `main`; HEAD `8b7596d docs(audioop): complete compatibility audit` (Phase 9 committed between sessions).
- Working tree now contains Phase 10 additions and the two README accuracy fixes; `git diff --stat` for the benchmark+docs portion of Phase 10 is `9 files changed, 6 untracked` (see §22); no deletions.

## 24. Explicit confirmation

**No commit, push, tag, release, or history rewrite was performed during this phase.** All changes are uncommitted in the working tree.

## 25. Phase verdict and recommendation

**PHASE 10 COMPLETE — READY FOR RELEASE REVIEW.**

The completion criteria are met: all 26 operations were benchmarked; every reported number passed its correctness gate; three paths plus a separately-labelled CLI path are compared without conflation; repeated runs and stability are reported with the noisy cells named; raw data and environment metadata are retained; performance claims are evidence-based (including the honest finding that C is typically 3–10× faster than the current Mojo port); the opcode registry matches the implementation 1:1; release-readiness documentation exists; and the full validation suite passes.

I recommend proceeding to release review with **v0.1.0** as the version number and **no performance-based release blockers**. The next step is the release mechanics themselves (tag, GitHub release, package metadata) — explicitly out of scope for this phase and tracked separately.
