# Benchmark design: PyroMojo Resampy v0.1.0

**Phase 1 deliverable — benchmark methodology specification.**
**Reference:** `resampy` 0.4.3, commit `7c484f8eec54b87e8f566578dc3e48a2be81cc80`.
**Status:** specification only. **No benchmarks were run in Phase 1.**

**Labels:** `[V]` verified from source · `[I]` engineering decision/recommendation ·
`[U]` unresolved/unverified.

**Related Phase 1 documents:** [reference-audit.md](reference-audit.md) · [api-scope.md](api-scope.md) · [licensing-audit.md](licensing-audit.md) · [library README](../README.md).

---

## 1. Resolving the methodology discrepancy `[V]` + `[I]`

Phase 0 identified a conflict. Verified evidence:

| Source | Stated comparison model |
|---|---|
| `docs/benchmarks/README.md:15-25` ("binding for any performance number") | **three paths**: (1) Python reference, (2) native Mojo, (3) **Mojo from Python interop**; "Where a path is not yet available, the report states the gap explicitly instead of omitting it." |
| `libraries/resampy/README.md:42` (placeholder) | "Three-way comparison: Python reference, native Mojo, **Mojo via Python interop**." |
| Actual shipped benchmark — `libraries/audioop/benchmarks/run_benchmarks.py:1-12` | **four labelled paths**: pure-Python floor, CPython 3.12.3 C-backed reference, native Mojo kernel (in-process `bench.mojo`), and a **separately measured CLI/protocol path** ("never presented as kernel performance"). Correctness gate: `pure == CPython == Mojo`, exact. |
| `libraries/bitarray/benchmarks/README.md`, `docs/benchmarks/releases/levenshtein-v0.1.md`, `msgpack-v0.1.md` | pure Python / optimized C or C++ / native Mojo (three-way), with a separately measured CLI path in audioop. |
| `scripts/run_all_benchmarks.py` | **stub**, `return 2` — no orchestrator exists. Both `.github/workflows/{tests,benchmarks}.yml` are placeholders that never build Mojo. |

Two distinct issues:

1. **Terminology:** "three-way" means *different things*. The binding doc counts
   "Mojo from Python interop" as a path; shipped ports count a **pure-Python
   floor** and an **optimized native reference** instead, and measure CLI
   overhead separately. `[V]`
2. **Resampy has no separate pure-Python or C reference.** `[V]` Upstream
   Resampy's interpolation loop is Numba-compiled
   (`resampy/interpn.py`: `@guvectorize(..., nopython=True)` +
   `jit(nopython=True, nogil=True, parallel=...)`). There is **no pure-Python
   fallback** in 0.4.3 and no upstream C extension. So "path 1" (Python
   reference) and "path 2" (compiled/JIT) are, for Resampy, **the same code**
   observed at different lifecycle stages (cold JIT compile vs warm execution).

**Decision `[I]` — adopt a four-path model for Resampy, and record the deviation
from `docs/benchmarks/README.md` explicitly in the report:**

| # | Path | What it measures | Provenance |
|---|---|---|---|
| 1 | **Upstream Python Resampy (sequential, `parallel=False`)** | warm steady-state kernel of the pinned reference, timed in-process | upstream `resampy.resample` |
| 2 | **Upstream Numba JIT / parallel path** | (a) cold JIT compilation of the gufuncs; (b) optional `parallel=True` variant | upstream `resampy.interpn` (`resample_f_s`, `resample_f_p`) |
| 3 | **Native Mojo kernel** | in-process `bench.mojo` timing, fresh output buffer per workload | PyroMojo port |
| 4 | **CLI/process overhead** | per-request framed CLI path (process spawn + framing + kernel) | PyroMojo framed CLI |

Plus an optional **PyroMojo-authored pure-Python/NumPy floor** (path 0), written
in the style of `libraries/audioop/benchmarks/pure_python_reference.py` — but
`[I]` it must be **clearly labelled as a PyroMojo reimplementation, not an
upstream implementation**, and it must pass the same correctness gate. It exists
only to make the "slower than pure Python" comparison meaningful; it is not
required for correctness and should be deferred if it risks confusion.

`[I]` **Do not** treat "Mojo from Python interop" as a measured path for
v0.1.0 (see §3). The binding doc's requirement is satisfied by explicitly
reporting that path as **unavailable/unverified** rather than omitting it
silently (`docs/benchmarks/README.md:24-25`).

---

## 2. Fairness requirements `[I]` (aligned with `docs/benchmarks/README.md` §"Fairness rules")

- Identical logical inputs (bit-identical input signal, identical `sr_orig`,
  `sr_new`, `filter`) for every path.
- Identical validation and identical correctness gate for all paths before any
  timing is recorded (§5). For a future upstream comparison the gate is
  **tolerance-based**, not exact — see `api-scope.md` §6. Phase 4
  local-reference tests are exact.
- No pre-computation unless every path gets the same pre-computation. Filter
  loading/caching must be identical in status across paths; report whether
  each path starts with a cold or warm filter cache.
- Reference code used as published, without hand-tuning beyond documented
  configuration (`parallel=False` default, `filter='kaiser_fast'`).
- Failures, timeouts, unsupported cases reported, not dropped.
- Any deviation from `docs/benchmarks/README.md` listed in the report
  (this §1 decision is the principal one).
- **No misleading speedup claims:** never compare a warm Mojo kernel against a
  cold/JIT-compiling reference call, never present CLI-inclusive time as kernel
  time, never publish single-run numbers, and always state medians + dispersion.

---

## 3. Is Python-to-Mojo interop viable with Mojo 1.2.0? `[V]` + `[U]`

The task requires this not to be assumed. Verified local evidence:

- `experiments/interop_benchmark/interop.mojo` registers exactly **one**
  exported function, `prng_checksum`, via `PythonModuleBuilder` /
  `@export` / `abi("C")`. `[V]`
- `experiments/interop_benchmark/benchmark_smoke.py`, `diagnose_timing.py`,
  `inspect_interop.py`, and `scaling_test.py` call
  `interop.sum_squares_batch(...)`, **which `interop.mojo` does not define**.
  Only `benchmark_recurrence.py` and `recurrence_test.py` call the function
  that actually exists (`prng_checksum`). `[V]`
- `pyproject.toml:43-49` calls these "**Legacy Mojo-interop experiments**" and
  excludes them from ruff; `scripts/run_all_benchmarks.py` is a stub; no CI
  workflow builds Mojo. `[V]`
- No recorded output/result artifact exists in
  `experiments/interop_benchmark/`. `[V]`

**Conclusion `[I]`:** the repository contains **no verified, working
Python-to-Mojo interop benchmark** for float/array payloads. Mojo 1.2.0's
`PythonModuleBuilder` scalar path (`prng_checksum`) is present in source but
its current buildability and its ability to exchange NumPy float arrays were
**not** demonstrated. `[U]` Whether a fair interop path is technically viable
is an open question.

**Decision `[I]`:** for v0.1.0, do **not** include an interop path; report it
as unavailable with the evidence above. Re-evaluate in Phase 2 only via a
dedicated toolchain probe that (a) builds `interop.mojo` with `.venv/bin/mojo`
1.2.0, (b) proves bidirectional float-array marshalling, and (c) passes the
same correctness gate. Until then, path 4 (framed CLI) is the only verified
Python↔Mojo bridge in this repository (audioop precedent).

---

## 4. Input workloads `[I]`

Workloads are generated once from a recorded seed (following audioop's
`seed 20260610` convention) and shared by all paths. Sizes are proposals,
bounded by the 64 MiB frame cap (`MAX_FRAME_BYTES` in the shipped ports) and by
untested extreme-ratio behaviour (`reference-audit.md` §4).

| Dimension | Proposed values | Rationale |
|---|---|---|
| Signal length (samples) | `0?` no (invalid), `1?` no (downsample invalid), `2`, `16`, `64`, `256`, `1024`, `4096`, `16384`, `65536` | short/edge + realistic 20 ms audio frames + long signals; matches bitarray/audioop size ladders. Very long (>65536) deferred to avoid pure-Python path wall time. |
| Signal content | silence (all-zero), impulse (single 1.0), constant/DC, sine (several frequencies below Nyquist), chirp/log sweep, white noise (seeded), ramp, full-scale square | covers boundary/zero-extension, spectral content, and quality-test analogues (`tests/test_quality.py` uses sine/sweep). |
| `sr_orig : sr_new` ratios | up `1:2`, `1:4`, `1:3`; down `2:1`, `4:1`, `3:2`; non-integer `22050:16000`, `44100:16000`, `12499:15001`; matched `1:1` (copy path) | covers `scale=1`, `scale<1`, non-integer ratios, and the documented length-rounding case (#111). |
| Filter | `kaiser_fast` (v0.1 in-scope); record `kaiser_best` as deferred/not run | `api-scope.md` §4. |
| Channels/axis | **1-D only** for v0.1.0; multi-channel deferred | `api-scope.md` §5. |
| dtype | float64 only for v0.1.0 | `api-scope.md` §4. |

`[U]` Extreme ratios (e.g. `sr_new/sr_orig < 1/P` ⇒ `index_step=0`) are
excluded from v0.1 workloads pending Phase 2 probing; if included, any failure
must be reported, not dropped.

Every workload must record: seed, exact input bytes (hex/base64 IEEE-754),
`sr_orig`, `sr_new`, filter, dtype, expected output length, and reference
output checksum. `[I]`

---

## 5. Correctness gate before timing `[I]` (mandatory)

No timing is recorded until the gate passes. Proposed gate (calibrate in Phase
2 — see `api-scope.md` §6 `[U]`):

1. **Length:** all paths produce exactly `int(L*float(sr_new)/float(sr_orig))`
   samples. Exact integer equality.
2. **Values:** for a future upstream comparison, compare Mojo output to the
   pinned 0.4.3 reference using the documented tolerance — Phase 1 proposal
   `max_abs <= 1e-9`, `atol=rtol=1e-9` for float64/`kaiser_fast`; **record**
   `max abs error`, `RMSE`, and the number of elements exceeding the tolerance.
   These are **proposals, not measured values**, and must be frozen only after
   real upstream outputs are compared. Phase 4 local-reference tests are exact.
3. **NaN/Inf:** position-wise match where defined; documented exclusions.
4. **Equal-rate path:** bit-identical copy.
5. **Determinism:** same input → identical Mojo output across repeated runs.
6. Record the gate result per cell (`PASS`/`FAIL`) in the raw results; a FAIL
   aborts that cell and is reported, never silently dropped.

This replaces the exact-equality gate used by the four shipped ports, because
Resampy's output is floating-point and a native port cannot be assumed
bit-identical to a Numba/LLVM-compiled reference. `[I]`

---

## 6. Measurement methodology `[I]`

| Aspect | Rule |
|---|---|
| Timing method | `time.perf_counter_ns` in-process for Python paths; Mojo kernel timed **in-process inside `bench.mojo`** (audioop precedent), with a per-cell sink/checksum to prevent dead-code elimination; CLI path timed per request with `subprocess` + `time.perf_counter_ns`. |
| Warm-up | ≥5 warm-up iterations discarded (matching `benchmarks/config.json` in msgpack/levenshtein/bitarray: `warmup: 5`, `samples: 25`). Mojo: warm the kernel and filter table before measuring. |
| Repetitions | ≥25 measured samples per cell per run, ≥2 independent runs (`--runs 2` in audioop). Report **median-of-medians**; report min/max and dispersion. |
| Aggregation | Per-cell medians; per-operation **geometric means** only for summary tables, with the full per-cell table authoritative (audioop `BENCHMARK_REPORT.md` §2). Never report a single run. |
| **Cold compilation (Mojo)** | Build `bench.mojo` / `cli.mojo` from a clean state, record wall-clock compile time and toolchain version, **separately** from warm execution. `docs/benchmarks/README.md:37-46`. |
| **JIT compilation (Numba)** | `[V]` `interpn.py` uses `jit`/`guvectorize` with **no `cache=True`**, so the gufuncs compile on first call in each process. Record the first-call latency as cold JIT; **exclude it from warm timings**; force compilation via an explicit warm-up call before the measured region, per cell dtype/shape signature. Report JIT compile count/time. Never compare warm Mojo against a cold reference. |
| **Process/CLI overhead** | Measured separately per request (process spawn + framing + kernel). Report the ping/empty-frame floor (~16 ms in audioop) and state explicitly it is **not kernel performance**. |
| Memory | `[I]` Record peak RSS where feasible (allocation-sensitive: output length scales with ratio, filter table 12,289 float64 ≈98 KB for `kaiser_fast`); note that the shipped ports do not yet have a shared memory harness — `[U]` feasibility. |
| Environment metadata | Commit SHA of PyroMojo, pinned `resampy==0.4.3` + upstream commit, exact `numpy`/`numba` versions, Python interpreter version/build, Mojo 1.2.0 (`2016d0cd`), CPU model/core count, OS, `taskset` pinning, seed, config file, warm-up/iteration counts, aggregation method — written to `results/environment.json`. `docs/benchmarks/README.md:51-60`. |
| Pinning | `[I]` Pin benchmark subprocesses with `taskset` to the least-loaded cores (audioop precedent); record that no frequency locking is used and residual noise is environmental. |
| Raw data | `results/raw_results.json`, `results/summary.csv`, `results/environment.json`; curated `reports/BENCHMARK_REPORT.md`. Generated scratch data git-ignored (`.gitignore:36-41`). |

---

## 7. Report template `[I]` (follow `docs/benchmarks/README.md` §"Reporting template")

1. Summary (with the §1 four-path decision and explicit interop gap).
2. Environment (all metadata above).
3. Configuration (workloads, seed, filter, dtype, tolerance gate).
4. Correctness gate results (per-cell PASS/FAIL + error metrics).
5. Results tables: per-cell medians for paths 1–4, per-operation aggregates,
   content/size sweeps, variance across runs.
6. Analysis: where Mojo wins/loses, identified causes (allocation, scalar vs
   vectorised kernels, filter-table size), no universal-speedup claim.
7. Limitations: JIT/compile treatment, shared-machine noise, deferred
   `kaiser_best`/multi-channel/float32, `[U]` interop.
8. Reproduction commands and deviation list.

Cold compilation, JIT compilation, process spawn and warm kernel time are
**never combined into a single number**. `[V]` `docs/benchmarks/README.md:39`.

---

## 8. Known limitations `[U]` / `[I]`

- `[U]` Interop path (§3) — unverified; excluded for v0.1.0.
- `[U]` Exact future-upstream tolerance values must be calibrated against real
  0.4.3 outputs in a pinned reference venv; nothing was measured in Phase 1.
- `[U]` Reference interpreter/dependency versions (NumPy/Numba on Python 3.12
  vs 3.13) not yet selected; Numba JIT behaviour varies by version and can
  change both warm timings and last-bit results. `setup.cfg` minimum
  `numba>=0.53` (0.53.0 itself requires Python `<3.10`); a modern pinned
  Numba is needed for a 3.12/3.13 reference venv — Phase 2 decision, **no
  installation performed**.
- `[I]` No shared benchmark orchestrator exists (`scripts/run_all_benchmarks.py`
  stub); Resampy needs a per-library `benchmarks/run_benchmarks.py` driver,
  invoked manually. CI cannot currently run Mojo benchmarks.
- `[I]` `kaiser_best` (3.2 MB table), multi-channel, float32, complex, and
  `parallel=True` are out of v0.1 scope; their absence must be stated, not
  hidden.
- `[I]` Pure-Python floor (path 0) is PyroMojo-authored, not upstream; if
  included it must be labelled to avoid implying it is Resampy code.
- `[V]` Shared-machine noise is documented in
  `libraries/audioop/benchmarks/reports/BENCHMARK_REPORT.md:608`; medians-of-
  medians mitigate but do not eliminate it.

---

## 9. Explicitly not done in Phase 1 `[V]`

No benchmarks executed, no benchmark scripts modified, no workloads/generators
created, no `bench.mojo` written, no dependencies installed, no CI changes, no
`docs/benchmarks/README.md` edit (the §1 deviation is recorded here for
maintainer decision). **Do not run performance benchmarks until Phase 2+.**
