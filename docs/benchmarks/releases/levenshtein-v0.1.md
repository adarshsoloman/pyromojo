# Benchmark release: Levenshtein v0.1

Native Mojo port vs naive pure-Python DP vs RapidFuzz pure-Python
fallback vs RapidFuzz optimized C++, measured 2026-11-12 on the machine
below. This is a curated release summary; the raw 25-sample datasets
live in the (git-ignored) `*.bench.json` reports produced by the
driver, and the full methodology is in
`libraries/levenshtein/PHASE2_RESULTS.md`.

## Headline findings

- **Distance: Mojo beats the `_py` fallback everywhere (3–25x) and
  naive Python by two to three orders of magnitude** (0.0024x on
  `long_ascii_random`), but **trails C++ 3–9x on random content**.
  The gap explodes on equal/near-equal inputs (533x on
  `huge_ascii_equal`, 359x on `huge_ascii_onesub`): RapidFuzz trims
  common affixes before its bit-parallel core while Mojo always runs
  the full computation. Affix trimming is the top optimization
  proposal, reported as a limitation, not fixed in this phase.
- **Myers beats DP everywhere that matters** (8–59x at n≥64; 420 µs vs 24.4 ms at n=2048). It loses only at n≤7 where table setup dominates
  — sub-microsecond either way. The internal comparison isolates the
  algorithm: production `distance` tracks Myers within ~4% at large n.
- **Ratio is the honest loss.** Mojo uses DP-LCS; C++ uses bit-parallel
  LCS, so Mojo/C++ grows from ~2.5x at n=12 to ~200–250x at n≥256
  (equal-input spikes reach 18344x via the same trimming mechanism).
  Against the `_py` fallback Mojo wins clearly at small sizes
  (up to n≈31) and loses increasingly after the n≈64 crossover
  (14x at n=2048). A blocked bit-parallel LCS
  is proposed, not implemented.
- **Hamming scales linearly on both sides; Mojo loses on per-element
  cost** (1.1x at n=12 → 36x at n=2048): C++ is vectorized and nearly
  flat (140 ns → 511 ns); Mojo pays two O(n) code-point
  materializations plus bounds-checked indexing (~9 ns/element). Still
  2–8x faster than `_py` and naive everywhere. A
  materialization-free hamming is proposed.
- **Unicode costs nothing measurable.** Accent/CJK/emoji/combining
  workloads sit on the same scaling curves as ASCII at equal
  code-point counts. Argument order does not matter (both orders
  measured; run-1 asymmetry on one hamming pair was noise — run 2:
  4.01x vs 4.10x, run 3: 5.60x vs 5.57x).

No universal-MoJo-faster claim is made. Directions reproduce across three runs except near-parity cases
(all within 0.4–1.4x, all sub-microsecond or crossover-zone);
details in `PHASE2_RESULTS.md`.

## Environment

| Item | Value |
|---|---|
| CPU | AMD Ryzen 7 6800H with Radeon Graphics (16 cores) |
| Memory | 15528948 kB |
| OS | Linux-7.0.0-28-generic-x86_64-with-glibc2.39 |
| Python | 3.13.14 |
| RapidFuzz | 3.14.6 (C++ and `*_py` from the same package) |
| Mojo | 1.2.0 (2016d0cd) |
| Git | 5700467 (working tree includes uncommitted Phase 1–2 files) |
| Timer | `time.perf_counter_ns` (Python), `std.time.perf_counter_ns` (Mojo) |
| Seed / warmup / samples | 20260202 / 5 / 25 |
| Naive cell budget | 65536 (naive DP skipped above 256×256; `n/a`) |

## Configuration

Workloads are defined in `libraries/levenshtein/benchmarks/workloads.py`
and selected in `libraries/levenshtein/benchmarks/config.json`
(seed 20260202, warmup 5, samples 25). Each pair is processed by all
paths; correctness is verified outside every timed region (exact
integers; bit-exact float64 ratio via packed `>d` bits; identical
hamming error text; a live Phase-1 CLI error-frame probe). Native timing
is in-process (`bench.mojo`); framing I/O, process startup, and IPC are
excluded. Production `distance`/`ratio`/`hamming` include one O(n+m)
code-point materialization per call; the internal DP-vs-Myers
comparison excludes it by construction.

## Distance results

Speedup convention: each ratio is `Mojo time / other time` computed on
medians. Below 1.0 means Mojo is faster. Medians with min/max ns, plus
ops/s:

| workload | naive med ns (min/max) | py med ns | cpp med ns | mojo med ns (min/max) | mojo ops/s | Myers/DP | Mojo/C++ | Mojo/py | Mojo/naive |
|---|---|---|---|---|---|---|---|---|---|
| short_ascii_random 12x12 | 14557 | 4127 | 210 | 661 (641/761) | 1,512,859 | 0.65x | 3.15x | 0.16x | 0.05x |
| medium_ascii_random 64x64 | 333621 | 35707 | 361 | 3326 (3236/3757) | 300,661 | 0.11x | 9.21x | 0.09x | 0.01x |
| long_ascii_random 256x256 | 5105713 | 193005 | 3818 | 12354 (12143/12633) | 80,945 | 0.03x | 3.24x | 0.06x | 0.00x |
| xlong_ascii_random 1024x1024 | n/a | 1213134 | 33534 | 115598 (114958/139324) | 8,651 | 0.02x | 3.45x | 0.10x | n/a |
| huge_ascii_random 2048x2048 | n/a | 3658336 | 124316 | 427308 (419743/825932) | 2,340 | 0.02x | 3.44x | 0.12x | n/a |
| huge_ascii_equal 2048x2048 | n/a | 4304658 | 812 | 432658 (425144/818738) | 2,311 | 0.02x | 532.83x | 0.10x | n/a |
| huge_ascii_onesub 2048x2048 | n/a | 4292095 | 1182 | 424903 (414494/1099298) | 2,353 | 0.02x | 359.48x | 0.10x | n/a |
| unequal_lengths 48x160 | 607418 | 90251 | 631 | 5470 (4288/10811) | 182,815 | 0.07x | 8.67x | 0.06x | 0.01x |
| unicode_cjk 48x48 | 234464 | 29866 | 401 | 1964 (1924/9067) | 509,165 | 0.10x | 4.90x | 0.07x | 0.01x |
| emoji_astral 54x48 | 286221 | 30468 | 411 | 1934 (1893/2034) | 517,063 | 0.12x | 4.71x | 0.06x | 0.01x |
| size_0064_random 64x64 | 336106 | 35828 | 531 | 3276 (3216/3718) | 305,250 | 0.11x | 6.17x | 0.09x | 0.01x |
| size_0065_random 65x65 | 341426 | 35948 | 882 | 5611 (5490/6152) | 178,221 | 0.12x | 6.36x | 0.16x | 0.02x |
| size_2048_random 2048x2048 | n/a | 3652545 | 113254 | 430874 (425865/867149) | 2,321 | 0.02x | 3.80x | 0.12x | n/a |

(Full 41-workload median tables live in `PHASE2_RESULTS.md`.)

## Ratio results

Same `Mojo time / other time` convention (below 1.0 = Mojo faster).
Mojo ratio is DP-LCS; the gap to bit-parallel C++ is the known
algorithmic deficit:

| workload | py med ns | cpp med ns | mojo med ns (min/max) | Mojo/C++ | Mojo/py | Mojo/naive |
|---|---|---|---|---|---|---|
| short_ascii_random 12x12 | 2965 | 231 | 781 (721/822) | 3.38x | 0.26x | 0.09x |
| medium_ascii_random 64x64 | 11792 | 280 | 15910 (15900/15941) | 56.82x | 1.35x | 0.07x |
| long_ascii_random 256x256 | 55555 | 1082 | 246566 (245103/289217) | 227.88x | 4.44x | 0.07x |
| xlong_ascii_random 1024x1024 | 252617 | 16591 | 3954677 (3877632/4699455) | 238.36x | 15.65x | n/a |
| huge_ascii_random 2048x2048 | 715463 | 64532 | 12791945 (12567350/13218031) | 198.23x | 17.88x | n/a |
| huge_ascii_equal 2048x2048 | 791316 | 882 | 16179028 (16024557/17346505) | 18343.57x | 20.45x | n/a |
| unicode_cjk 48x48 | 11833 | 411 | 7394 (7374/13525) | 17.99x | 0.62x | 0.05x |
| combining 40x40 | 8696 | 340 | 4969 (4959/4990) | 14.61x | 0.57x | 0.05x |
| size_0064_random 64x64 | 13235 | 291 | 16000 (15980/24967) | 54.98x | 1.21x | 0.08x |
| size_2048_random 2048x2048 | 923106 | 65264 | 13030935 (12654704/14106568) | 199.66x | 14.12x | n/a |

## Hamming results

Same convention. Both sides scale linearly; the gap is per-element cost
(vectorized C++ vs Mojo's double materialization + checked indexing):

| workload | py med ns | cpp med ns | mojo med ns (min/max) | Mojo/C++ | Mojo/py | Mojo/naive |
|---|---|---|---|---|---|---|
| short_ascii_random 12x12 | 661 | 160 | 160 (150/190) | 1.00x | 0.24x | 0.24x |
| medium_ascii_random 64x64 | 3907 | 331 | 641 (631/651) | 1.94x | 0.16x | 0.17x |
| long_ascii_random 256x256 | 14768 | 431 | 2335 (2324/2364) | 5.42x | 0.16x | 0.17x |
| xlong_ascii_random 1024x1024 | 38112 | 341 | 9057 (9037/9137) | 26.56x | 0.24x | 0.30x |
| huge_ascii_random 2048x2048 | 78468 | 531 | 18175 (18154/19196) | 34.23x | 0.23x | 0.27x |
| unicode_cjk 48x48 | 2935 | 160 | 751 (741/801) | 4.69x | 0.26x | 0.27x |
| size_0064_random 64x64 | 1964 | 160 | 641 (631/651) | 4.01x | 0.33x | 0.34x |
| size_2048_random 2048x2048 | 78288 | 531 | 18395 (18244/19787) | 34.64x | 0.23x | 0.30x |

## Compilation and memory (separate from runtime)

| Metric | Value |
|---|---|
| Cold compile (`mojo build bench.mojo`, no prior artifact) | 1.2 s / 2.8 s / 2.8 s across runs 1–3 (page-cache variance, stated) |
| Executable size | 93144 bytes (both runs) |
| Peak RSS, distance on `huge_ascii_random` (isolated child) | 14213120 B / 14258176 B / 14688256 B |

RSS includes process startup and the Mojo runtime; it is not
allocator-only. The frame itself is ~4 KB — RSS is dominated by
runtime, not input.

## Analysis

- Production distance tracks Myers within ~4% at large n; conversion
  overhead is visible only at tiny sizes. The internal comparison is
  clean: Myers wins 8–59x over DP from n≈31 upward.
- The C++ advantage concentrates in two mechanisms Mojo lacks:
  common-affix trimming (equal/near-equal spikes) and SIMD-width
  bit-parallelism with lower per-op overhead (the steady 3–9x on random
  content, plus the C++ 64→65 word-step doubling visible in the sweep).
- The fallback comparison is reported for completeness only: Mojo is
  3–25x faster on distance, loses increasingly on ratio past n≈64,
  and is 2–8x faster on hamming. The C++ column is the real baseline.
- Unicode handling costs nothing measurable: non-ASCII workloads sit on
  the ASCII scaling curves at equal code-point counts.

## Limitations

- Sub-100-microsecond medians vary run to run (notably C++ on tiny
  payloads and the 64×64 hamming triple-coincidence in run 1, which run
  2 resolves into distinct distributions); directions reproduce except
  five near-parity cases — read small magnitudes with their min/max
  bands.
- Page cache was warm for compilation; CPU frequency scaling was not
  pinned.
- Weighted distance and unpadded-hamming error paths are
  correctness-gated (goldens + live CLI probe) but not timed.
- No adversarial or pathological-input performance characterization.
- The Mojo-from-Python interop path from the methodology doc is not
  measured (`ctypes`/`PythonModuleBuilder` are out of project scope).

## Reproduction

```bash
uv sync --extra dev
.venv/bin/python libraries/levenshtein/benchmarks/run_benchmarks.py
```

Options: `--only a,b`, `--warmup N`, `--samples N` (>= 25), `--config`,
`--raw-out`. Raw samples plus metadata are written to
`build/levenshtein-bench.bench.json` (git-ignored). The driver deletes
the old binary before building, so the reported compile time is fresh
every run (page cache stays warm; this is stated, not hidden).
