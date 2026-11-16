# Audioop benchmarks

Three-way performance comparison for the native Mojo audioop v0.1.0 port:
pure-Python baseline vs CPython 3.12.3 C `audioop` (ceiling) vs native
Mojo kernel (in-process `bench.mojo`) vs the Mojo CLI request path
(measured separately, never conflated with kernel numbers).

This is a measurement and documentation phase. No implementation code
was changed to obtain these numbers.

## 1. Benchmark objectives

Establish honest, reproducible performance characteristics for all 26
audioop operations: where native Mojo beats pure Python, where it beats
or (usually) trails the C reference, how costs scale with input size,
and what the CLI process+framing overhead floor looks like.

## 2. Implementations compared

- **pure** — `pure_python_reference.py`: transparent per-sample Python
  loops mirroring the documented CPython algorithms (GETSAMPLE32 scaling
  included), no NumPy/Cython/Numba, no calls into CPython `audioop`.
  Gated byte-for-byte against CPython on all 250 benchmark workloads.
- **c** — CPython 3.12.3 `audioop` C extension, executed in-process inside
  a long-lived reference-venv worker (`reference_worker.py`), timed with
  `time.perf_counter_ns` so no IPC cost enters the measurement.
- **mojo** — the released native Mojo operations
  (`libraries/audioop/mojo/`), timed in-process by `bench.mojo`. Each
  workload runs in a fresh process with input bytes parsed once outside
  the timed region; 5 warmup + 25 measured iterations per cell.
- **cli** — the `audioop_cli` binary driven over its framing protocol
  (15 samples per cell). This measures process spawn + framing + kernel;
  `ping` (empty `0x01` frame) is measured separately as the floor.

## 3. Hardware and software environment

Recorded per run in `results/environment.json` (reference run:
Python 3.13.14 host, CPython 3.12.3 reference, Mojo 1.2.0
(`2016d0cd`), AMD Ryzen 7 6800H, 16 cores, Linux 7.0.0-28-generic,
`uv` environment, git `8b7596d`, seed `20260610`, timer
`time.perf_counter_ns`). Your numbers will differ by machine; the
workload definitions and seeds are fixed.

## 4. Workloads

`workloads.py` builds 250 deterministic cells (`FNV-1a` checksummed,
`seed 20260610`):

- Sizes: 160 frames (20 ms @ 8 kHz), 4096, 65536 frames (small/medium/
  large). The design doc's 1-Mi-frame tier is deferred: at 65536
  frames the pure-Python floor already dominates wall time.
- Content: silence, full-scale square, sine, uniform random, sparse
  (1% non-zero), ramp, clipped, impulses. The primary matrix uses
  uniform random; a content sweep runs the representative subset on
  width-2 medium fragments.
- Widths 1/2/4 where the operation supports them; stereo pairs for
  `tomono`, 2-channel `ratecv`; `find*` windows 1/8/64 with 4×
  fragments; `getsample` first/middle/last; `ratecv` at
  8k→16k, 16k→8k, 44100→48000 with cold and warm state.

`lin2adpcm`/`adpcm2lin` nan/oversize and `mul` NaN cases are excluded
per the frozen Phase 0 undefined-behaviour policy (documented
Mojo NaN→0 semantics; no compatibility claim).

## 5. Correctness gates (hard fail)

Every benchmarked cell must pass a three-way gate before any timing is
reported: `pure == CPython C == Mojo`, exact bytes (and exact returned
state for `ratecv`/`adpcm*`). The gate compares the Mojo kernel output
against the reference on the same bytes the timed loop will process.
Any mismatch aborts the suite with a non-zero exit. 250/250 cells
passed in the reference run.

## 6. How to run

```bash
# Full suite (2 runs, gate + timing + report; several minutes)
.venv/bin/python libraries/audioop/benchmarks/run_benchmarks.py --runs 2

# Only regenerate the summary + report from existing results/
# (no new measurements; seconds)
.venv/bin/python libraries/audioop/benchmarks/run_benchmarks.py --report-only
```

Outputs:

- `results/raw_results.json` — every sample, every run, full env.
- `results/summary.csv` — per-cell medians-of-medians.
- `results/environment.json` — toolchain/host metadata.
- `reports/BENCHMARK_REPORT.md` — curated tables and analysis.

## 7. What the numbers mean (read before quoting)

- `mojo/pure > 1` means Mojo is faster than the pure-Python floor
  (expected: ~20–100×).
- `mojo/c < 1` means CPython C is faster than native Mojo (expected
  almost everywhere: ~3–10× in our runs). See the report's
  categorization section for the +/-10% tolerance rule.
- `cli` numbers include ~16 ms of process spawn (see `ping`) and must
  never be read as kernel performance.
- Run-to-run variance on this shared machine is large for small cells;
  headline numbers are medians-of-medians across runs, and the report
  lists the noisiest cells explicitly. Re-run on a quiet machine for
  tighter numbers.
