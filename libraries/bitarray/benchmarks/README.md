# Bitarray benchmarks

Three-way performance comparison for the native Mojo Bitarray v0.1.0
implementation: pure-Python baseline vs C-backed `bitarray==3.12.3` vs
released native Mojo code. This is a measurement and documentation
task; it changes no library implementation.

## 1. Benchmark objectives

Establish honest, reproducible performance characteristics for six
operations (`AND`, `OR`, `XOR`, `count`, left shift, right shift)
before presenting PyroMojo at the Modular Forum: where native Mojo
beats pure Python, where it beats or trails the C reference, and how
costs scale with input size.

## 2. Implementations compared

- **pure** — `pure_python_reference.py`: transparent list-of-`bool`
  operations, zero-fill shifts, `ValueError` on negative shifts. No
  NumPy, Cython, Numba, or other compiled acceleration.
- **c** — `bitarray==3.12.3`, verified to load the compiled
  `_bitarray` extension (`.so`), not a pure-Python fallback.
- **mojo** — the released `BitArray` operations on packed `UInt8`
  storage (`libraries/bitarray/mojo/`), timed in-process by
  `bench.mojo`. No alternate implementation exists for benchmarking.

## 3. Hardware and software environment

Recorded per run in the JSON report's `meta` section (reference run:
Python 3.13.14, `bitarray==3.12.3`, Mojo 1.2.0 (`2016d0cd`), AMD
Ryzen 7 6800H, 16 cores, ~15 GB RAM, Linux 7.0.0-28-generic, git
`87a3f6d`, `time.perf_counter_ns`). Your numbers will differ by
machine; the workload definitions and seeds are fixed.

## 4. Input sizes and distributions

- Sizes (bits): 64, 256, 1024, 4096, 16384, 65536, 262144, 1048576.
- Distributions: zeros, ones, alternating, sparse random (1% ones),
  dense random (99% ones), uniform random. Fixed seed (`20260610`);
  binary operands are drawn independently.
- Shift distances per size: 1, 8, 64, 25% of length, and the full
  length (deduplicated). `k = 0`, `k > n`, and negative `k` are
  correctness edge cases only, not timed workloads.
- Both endiannesses with logically identical sequences.

Sizes are multiples of 64, so the partial-byte tail path is exercised
for correctness (unit tests, golden vectors) but not isolated for
performance; all benchmarked arrays are byte-aligned.

## 5. Methodology

- Inputs are generated once and shared by all three implementations.
- Monotonic high-resolution clock (`perf_counter_ns`), 5 warmup runs,
  25 measured samples per cell.
- The Mojo binary is built once (cold-compile time reported
  separately); each cell runs one process whose internal loop is timed,
  excluding startup, framing I/O, and IPC. A per-iteration sink keeps
  the loop live; results are checksummed (FNV-1a) and hex-compared
  (n ≤ 4096) against the C reference outside the timed region.
- `validate_results.py` runs first as a hard gate (edge cases plus a
  randomized differential sweep); any failure stops the run.
- Timing gates: every sample must be positive with the configured
  count; Mojo medians must scale monotonically from 4096 bits upward.
- Throughput uses the logical bit length and the median sample.
  Speedup = baseline median / Mojo median (>1 means Mojo is faster).

## 6. Correctness validation

152 gate checks pass before timing: empty/one-bit/non-aligned arrays,
zero/at-length/over-length shifts, negative-shift errors, identical
and disjoint operands, both endiannesses, zeroed padding, plus
pure-vs-C equality on every benchmarked cell and Mojo checksum/hex
agreement on every timed cell.

## 7. Results

Full tables: [`results/bitarray_v0.1.0_summary.md`](results/bitarray_v0.1.0_summary.md);
machine-readable samples plus environment: [`results/bitarray_v0.1.0_results.json`](results/bitarray_v0.1.0_results.json).

Headline medians (uniform, big-endian; `pure / C / Mojo` ns, then
speedups vs pure and vs C):

| workload | pure | C | Mojo | vs pure | vs C |
|---|---|---|---|---|---|
| AND, 64-bit | 1833 | 110 | 50 | 37x | 2.2x |
| AND, 16 Kibit | 353385 | 190 | 2805 | 126x | 0.07x |
| AND, 1 Mibit | 24418369 | 34906 | 227489 | 107x | 0.15x |
| count, 64-bit | 321 | 120 | 20 | 16x | 6.0x |
| count, 16 Kibit | 54993 | 942 | 942 | 58x | 1.0x |
| count, 1 Mibit | 3297989 | 26510 | 59382 | 56x | 0.4x |
| shl@64, 16 Kibit | 56597 | 190 | 6031 | 9x | 0.03x |
| shr@64, 16 Kibit | 24997 | 190 | 4208 | 6x | 0.05x |

(Mibit = 2^20 bits, Kibit = 2^10 bits. Representative cells; every
cell is in the summary table.)

## 8. Performance analysis

Observed facts (each verified across both endiannesses and all six
distributions unless noted):

- **Mojo beats pure Python everywhere measured**, about 2x–205x
  (bitwise up to 205x, `count` 10x–58x, shifts 2x–22x except for the
  tie below). Packed bytes beat per-element Python objects at every
  scale; the only near-ties (~1x) are shifts by exactly the full
  length, where both sides just zero-fill (`[False] * n` is already
  C-speed on the Python side).
- **Mojo matches or beats C at 64 bits** (AND 50 ns vs 110 ns, count
  20 ns vs 120 ns, worst op 1.0x): call and dispatch overhead
  dominates both, and the tiny Mojo loop wins or ties.
- **Mojo ties C on mid-size `count`** (16 Kibit: 942 ns both) then
  falls behind ~2.3x at 1 Mibit (59 µs vs 26 µs).
- **Mojo trails C at scale on the rest**: ~6x–7x on bitwise ops at
  1 Mibit (AND: 227 µs vs 35 µs), ~10x–75x on shifts (16 Kibit:
  ~4–6 µs vs ~0.2–0.4 µs; 1 Mibit: ~0.3–0.5 ms vs ~4–43 µs). The C
  extension processes machine words (and vector units); the Mojo port
  walks bytes with per-element bounds checks, allocates a fresh
  result per call, and re-validates invariants. Single noisy
  sub-microsecond cells reach ~140x; the ranges above use stable
  large-size medians.
- **Shifts cost the same regardless of distance** (Mojo 16 Kibit
  `shl`: ~6.0 µs for k = 1..16384): every shift rewrites the whole
  buffer, so the run is memory-move dominated, not carry dominated.
- **Scaling is near-linear once overhead stops dominating**: Mojo
  AND costs 0.78 ns/bit at 64 bits, falling to ~0.2 ns/bit from 1 Kibit
  upward. At 64 bits, allocation plus dispatch (~30 ns, measured as
  the count-vs-AND delta) exceed the loop itself.
- **Endianness does not affect performance** (little/big median ratios
  0.99–1.05 across ops and sizes); bit density does not either at
  these scales (content-independent loops).

These are measured facts on the reference machine, not universal
claims. Sub-microsecond cells carry high relative dispersion
(median within-run stdev ~14–25% depending on implementation;
background load visibly moves them), so only large, repeated effects
are concluded above. A second full run reproduced the same workload
set and the same qualitative picture with median cell ratio 1.00.

Known limitation and future opportunity: the byte-serial loops with
fresh allocation are the bottleneck versus C's word-parallel kernels.
Word-at-a-time operations with masked tails (validated in Phase 0
probes) are the documented next step, deliberately not done here.

## 9. Known limitations

- Benchmark sizes are byte-aligned multiples of 64; non-aligned tail
  performance is not separately measured (correctness is covered).
- Pure Python is timed in-process like the others; no subprocess or
  CLI timing is included in the primary comparison.
- Timings are machine-specific; rerun on your hardware before quoting.
- Shift-by-zero, over-length, and negative shifts are validated for
  correctness only (`validate_results.py`), not benchmarked.

## 10. Reproduction

From the repository root (needs `.venv` with dev extras):

```bash
.venv/bin/python libraries/bitarray/benchmarks/validate_results.py
.venv/bin/python libraries/bitarray/benchmarks/run_benchmarks.py
```

The driver rebuilds `build/bench_bitarray`, runs the correctness gate,
times every cell (about 90 seconds on the reference machine), verifies
every Mojo result, and writes
`results/bitarray_v0.1.0_results.json` plus the summary Markdown.
`--sizes`, `--dists`, and `--samples` narrow a run for smoke-testing
(e.g. `--sizes 64 256 --dists zeros uniform --samples 5).
