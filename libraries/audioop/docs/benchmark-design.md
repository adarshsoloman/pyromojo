# Benchmark design: audioop v0.1 (proposal, not executed)

Phase 0 fixes the methodology; it runs no release benchmarks. Phase 1+
executes this design unchanged, following repository conventions:
deterministic inputs, in-process native timing, cold compile reported
separately, raw data git-ignored, curated summaries committed.

## 1. Paths to compare

1. **Naive baseline** — a pure-Python per-sample loop using
   `int.from_bytes`/`to_bytes` (an honest interpreter floor, not the
   reference).
2. **Reference** — CPython 3.12.3 `audioop` C extension, verified to be the
   pristine build (`verify_reference.py` proves equivalence).
3. **Native Mojo** — the ported operations, timed in-process by a
   `bench.mojo` harness with inputs ferried once outside timed regions.

Report `Mojo time / comparison time` on medians; below 1.0 means Mojo is
faster. Always per-operation tables, never one blended speedup.

## 2. Workload sizes

Frames per operation, chosen to cover boundaries and realistic audio:

- structural: 0, 1, 2, 3, 7, 8, 15, 16, 17 frames;
- audio-realistic: 160 (20 ms @ 8 kHz), 320 (20 ms @ 16 kHz), 882
  (20 ms @ 44.1 kHz), 960 (20 ms @ 48 kHz);
- bulk: 4096, 65536, 262144, 1048576 frames;
- stereo `tomono`/`tostereo` and `ratecv` use the same frame counts with
  `nchannels = 1` and `2`.

Widths 1, 2, 3 and 4 wherever the function accepts a width. Matching
functions (`findfactor`, `findfit`, `findmax`) are 16-bit only and are sized
in bytes as the reference requires.

## 3. Contents

Deterministic, seed `20260610`:

- silence (all zeros);
- full-scale square (`min`, `max` alternating);
- full-scale sine (integer-rounded);
- uniform random over the full width range;
- sparse random (1 % non-zero);
- ramp (monotonic);
- clipped/clamped input (to exercise saturation)
- alternating single-sample impulses.

Every content type is generated once per (width, frame count) and shared by
all three paths. Regeneration must be byte-identical across runs.

## 4. Operations measured

- Arithmetic: `add`, `bias`, `mul`, `tomono`, `tostereo`.
- Statistics: `max`, `minmax`, `avg`, `rms`, `cross`, `avgpp`, `maxpp`.
- Matching: `findfactor`, `findfit`, `findmax` (windows: 1, 8, 64 samples;
  fragment 4× reference).
- Fragments: `getsample` (first/middle/last), `byteswap`, `reverse`,
  `lin2lin` (every width pair, both directions).
- Codecs: `lin2ulaw`/`ulaw2lin`, `lin2alaw`/`alaw2lin`,
  `lin2adpcm`/`adpcm2lin` (round trips and one-way).
- Resampling: `ratecv` at 8→16 k, 16→8 k, 44.1→48 k, 48→44.1 k,
  1 and 2 channels, with `state=None` and with a warmed state.

Error paths are correctness cases, not speed workloads; one overhead sample
per error class is recorded separately.

## 5. What each measurement isolates

- **Core loop time**: pre-built input bytes, output allocation excluded by
  timing a recycled destination buffer where possible.
- **Total operation time**: includes the output allocation the public API
  performs; reported alongside core-loop time so allocator cost is visible,
  never hidden.
- **Stateful cost**: `ratecv`/ADPCM measured both cold (`state=None`) and
  warm (one state per 20 ms frame, 50 frames); per-frame overhead reported.
- **Cold compile**: `mojo build` wall time and binary size once per suite,
  never inside medians.
- **Python interop**: out of scope (same policy as the other ports); state
  the gap rather than measuring around it.
- **Startup**: process start excluded; timed loops are in-process.

## 6. Methodology and hygiene

- Inputs generated once, checksummed (FNV-1a), and hex-compared against the
  reference outside timed regions.
- `perf_counter_ns`; 5 warmup iterations, 25 measured samples per cell;
  medians and IQR reported; any non-positive sample fails the run.
- The Mojo binary is built once per suite; each cell runs in one process.
- CPU affinity pinned when available; hardware, OS, Python, Mojo commit, and
  git revision recorded in the JSON `meta` block.
- Run order interleaved per cell (reference, naive, Mojo) to reduce drift;
  at least two full suite runs for released numbers; a third if medians
  differ by more than 5 %.
- Raw results land in the git-ignored `benchmark_results/` tree; the curated
  `results.json` + `summary.md` are committed for a release.

## 7. Correctness gates (hard fail)

- Every benchmarked input must match the reference exactly on bytes and
  return values; a mismatch aborts the suite before timing is reported.
- Golden vectors (and the differential seed suite once it exists) must pass.
- Error messages for exercised error classes must match the reference.
- Undefined cases (`mul` with `nan`/`inf`) are excluded from equality gates
  and reported separately with the port's documented policy.

## 8. Performance targets (not gates)

Targets are hypotheses to falsify, never release claims:

| Group | Target vs reference |
| --- | --- |
| Samplewise arithmetic (`add`, `bias`, `mul`) | ≥ 1.0× |
| Statistics (`max`, `minmax`, `avg`, `rms`, `cross`, pp) | ≥ 1.0× |
| Fragment transforms (`byteswap`, `reverse`, `lin2lin`) | ≥ 1.0× |
| Codecs (u-law, A-law, ADPCM) | ≥ 0.7× |
| `ratecv` | ≥ 0.7× |
| Matching (`find*`) | ≥ 0.5× |

Below-target results are documented, not hidden; the C reference is the
ceiling, not a competitor to beat on principle.

## 9. Deliverables

- `benchmarks/bench.mojo` (native), `benchmarks/naive.py`,
  `benchmarks/run_benchmarks.py` (driver), `benchmarks/validate_results.py`
  (gate).
- `benchmarks/results.audioop_v0.1.0.json` and `benchmarks/summary.md`.
- A README stating hardware, versions, workload definitions, and the exact
  commands to reproduce.

## 10. Not benchmarked in v0.1

- Big-endian inputs (not supported in v0.1).
- Buffer-protocol / numpy inputs (out of scope).
- Streaming APIs beyond the reference's state tuples.
- SIMD/batched variants that do not exist yet.
