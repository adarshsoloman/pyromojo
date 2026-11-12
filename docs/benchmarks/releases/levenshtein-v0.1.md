# Benchmark release: Levenshtein v0.1.0

Native Mojo port vs naive pure-Python DP vs RapidFuzz pure-Python
fallback vs RapidFuzz optimized C++, measured 2026-11-12/13 on the
machine below. This is the curated v0.1.0 release summary; the raw
25-sample datasets live in the (git-ignored) `*.bench.json` reports
produced by the driver, the full methodology is in
`libraries/levenshtein/PHASE2_RESULTS.md`, and the optimization
history is in `libraries/levenshtein/PHASE3_RESULTS.md`.
The v0.1.0 numbers below are the post-optimization implementation.

## 1. Project overview

PyroMojo reimplements widely used Python libraries natively in Mojo
and subjects each port to the same bar: byte-level verification
against the pinned Python reference, a shared corpus of golden test
vectors, and reproducible benchmarks that report what was actually
measured. This release covers Levenshtein v0.1.0: edit distance,
Indel similarity ratio, and Hamming distance over Unicode strings.

## 2. Supported operations

Exactly three public operations (plus an integer-cutoff distance
variant), all over Unicode `str` input only:

- `levenshtein_distance(s1, s2, insertion=1, deletion=1,
  substitution=1)` — unit costs dispatch to blocked Myers
  bit-parallel; other positive-integer weights use the two-row DP.
- `levenshtein_distance_cutoff(s1, s2, score_cutoff, ...)` — exact
  `min(distance, cutoff + 1)`; negative cutoffs raise.
- `levenshtein_ratio(s1, s2)` — Indel normalized similarity
  (`1 - indel/(len1+len2)`); empty/empty is `1.0`.
- `levenshtein_hamming(s1, s2, pad=True)` — substitution count plus
  length difference when padding; `pad=False` with unequal lengths
  raises `ValueError("Sequences are not the same length.")`.

Out of scope for v0.1 (unchanged from the approved scope):
Jaro/Jaro-Winkler, normalized distance/similarity APIs, edit
operations and opcodes, matching blocks, median or median-improvement
algorithms, `StringMatcher`, similarity `score_cutoff`, `processor` /
`score_hint` parameters, and Python extension bindings. This release
is not a complete clone of the RapidFuzz package.

## 3. Algorithm architecture

- **Distance**: common-prefix/suffix trimming (exact for positive
  costs; validated on untrimmed inputs so the overflow guard keeps its
  documented meaning), then blocked Myers bit-parallel for unit costs
  (one `UInt64` word per 64 code points, shorter input as pattern) or
  two-row DP for weighted costs.
- **Ratio**: same affix trimming, then blocked bit-vector LCS
  (Hunt–Szymanski formulation, multiword subtract with explicit borrow,
  no shift ever reaches the bit width); normalization is exact
  float64 `1 - indel/total`.
- **Hamming**: single lockstep pass over both code-point iterators —
  no materialized arrays; lengths from `len(s.codepoints())` up front.
- **Oracle**: the two-row DP (`dp_distance`, `dp_lcs_length`) is
  retained, tested, and used as the independent correctness reference
  for both optimized paths.
- **Transport**: batch CLI over stdin/stdout with framed requests
  (`uint32 length | uint8 opcode | payload`), ASCII error messages on
  stdout, diagnostics on stderr; cutoffs/weights arrive as u64 and are
  range-checked (`weights` beyond `Int` range are rejected; a cutoff
  beyond `Int` range is exactly equivalent to no truncation and is
  treated as such).

## 4. Unicode behavior

Unit of comparison is the Unicode code point (never UTF-8 bytes, never
grapheme clusters), matching the reference exactly: no automatic
normalization (NFC `é` vs NFD `e`+combining-acute differ), astral emoji
count as single units, ZWJ sequences count per code point. Byte length
never enters any computation. Inputs that are not valid UTF-8 are
rejected at the frame boundary with an error frame; lone surrogates
and raw bytes are therefore unrepresentable by construction and
documented as deviations from the bytes-accepting reference.

## 5. Python-reference compatibility

Oracle: `rapidfuzz==3.14.6` (MIT; the GPL `Levenshtein` wrapper is
never imported or depended on). Compatibility is enforced at three
levels: 434 deterministic golden vectors (generated from the oracle,
drift-gated with `--check`, 432 exercised through the CLI plus 2
u64-inencodable negative cases covered natively); 24 Python
compatibility tests (CLI protocol, oracle assumptions, randomized
properties vs 205 fresh pairs); and per-benchmark correctness gates
(exact integers, bit-exact float64 ratio via packed `>d` bits,
identical hamming error text, live CLI error-frame probe). Phase 4
audit added 2470 adversarial differential cases (affix-heavy weighted
pairs, cutoff boundaries, Unicode edge cases) plus word-boundary
bit-pattern stress (sizes 1–256 around 64-bit words) and transport
edge cases — all matching, including a u64-max cutoff case that
exposed and fixed an over-strict CLI rejection.

## 6. Test coverage

- Native Mojo (`run_all_tests.py` builds and runs each): distance (8),
  ratio (3), hamming (4), Myers-vs-DP parity (5, incl. 450 randomized
  pairs), LCS-vs-DP parity (5, incl. 450 randomized pairs), trimming
  regression (10: identical/long affix/prefix-of-other/repeated/
  Unicode/weighted/cutoff/randomized), guards (4: word boundaries,
  overflow, float exactness, cutoff overflow), golden vectors (1 test,
  434 cases) — 40 tests, all passing.
- Python: 24 compat tests plus the full repo suite (153 pytest total:
  129 msgpack + 24 levenshtein), all passing.
- Fuzz coverage is differential and seeded (fixed seeds,
  reproducible), not unbounded.

## 7. Phase 2 benchmark baseline

Before optimization, the native implementation already beat the
pure-Python fallback everywhere on distance (3–25x) and naive DP by
two to three orders of magnitude, but trailed C++ 3–9x on random
content, with spikes on equal inputs (distance 533x, ratio 18344x:
RapidFuzz trims common affixes before its bit-parallel core while
Mojo ran the full computation). Ratio used O(n·m) DP-LCS (~200–250x
off C++ at n≥256); hamming materialized two code-point arrays (~36x
off vectorized C++ at n=2048).

## 8. Phase 3 optimization results

Three targeted, independently measured optimizations (each gated on
unchanged correctness):

| Optimization | Effect (new / Phase-2 baseline medians) |
|---|---|
| Affix trimming (distance) | 0.036x on identical 2048-char inputs (28x); 0.045x on near-identical; unchanged (0.97–1.05x) on random content |
| Blocked bit-parallel LCS + trim (ratio) | 0.022x at 2048 random (45x); identical inputs collapse ~1100x (16.7 ms → ~15 µs); faster at every size down to n=12 |
| Materialization-free hamming | 0.199x–0.647x on every workload (uniform ~2–5x win) |

No workload regressed beyond measurement noise (largest apparent
deltas: 1.5x on a 40 ns empty-input ratio, 1.09x on one 3 µs distance
case; both inside documented sub-microsecond variability and
non-reproducing across runs).

## 9. Mojo vs optimized C++ performance (v0.1.0, official run)

Speedup convention: each ratio is `Mojo time / C++ time` on medians.
Below 1.0 means Mojo is faster. Selected workloads (full 41-workload
tables in `PHASE2_RESULTS.md`/`PHASE3_RESULTS.md`):

| workload | distance | ratio | hamming |
|---|---|---|---|
| short_ascii_random 12x12 | 3.53x | 3.05x | 0.47x |
| medium_ascii_random 64x64 | 9.10x | 11.13x | 1.69x |
| long_ascii_random 256x256 | 3.24x | 10.60x | 5.27x |
| xlong_ascii_random 1024x1024 | 3.40x | 6.40x | 11.52x |
| huge_ascii_random 2048x2048 | 3.65x | 6.00x | 7.34x |
| huge_ascii_equal 2048x2048 | 18.88x | 17.34x | 15.43x |
| huge_ascii_onesub 2048x2048 | 9.52x | 16.10x | 15.94x |
| unequal_lengths 48x160 | 5.99x | 7.12x | 1.22x |
| unicode_cjk 48x48 | 4.88x | 4.90x | 2.25x |
| emoji_astral 54x48 | 4.64x | 4.57x | 1.27x |
| combining 40x40 | 4.16x | 3.86x | 1.56x |

Remaining gaps and their identified causes: equal-input distance/ratio
(large multiword setup + conversion vs C++ memcmp/short-circuit);
random-content distance (~3–9x: per-call setup, no SIMD); ratio
(~6–11x at n≥256: per-word overhead of the blocked implementation);
hamming (per-element bounds-checked iteration vs vectorized C++).
Unicode handling costs nothing measurable: non-ASCII workloads sit on
the ASCII scaling curves at equal code-point counts.

## Environment

| Item | Value |
|---|---|
| CPU | AMD Ryzen 7 680H with Radeon Graphics (16 cores) |
| Memory | 15528948 kB |
| OS | Linux-7.0.0-28-generic-x86_64-with-glibc2.39 |
| Python | 3.13.14 |
| RapidFuzz | 3.14.6 (C++ and `*_py` from the same package) |
| Mojo | 1.2.0 (2016d0cd) |
| Git | 4c2cf58 plus the documented uncommitted Phase-4 files (CLI cutoff clamp + regression test) |
| Timer | `time.perf_counter_ns` (Python), `std.time.perf_counter_ns` (Mojo) |
| Seed / warmup / samples | 20260202 / 5 / 25 |
| Naive cell budget | 65536 (naive DP skipped above 256×256; `n/a`) |

## Configuration

Workloads are defined in `libraries/levenshtein/benchmarks/workloads.py`
and selected in `libraries/levenshtein/benchmarks/config.json`.
Each pair is processed by all paths; correctness is verified outside
every timed region (exact integers; bit-exact float64 ratio via packed
`>d` bits; identical hamming error text; a live CLI error-frame
probe). Native timing is in-process (`bench.mojo`); framing I/O,
process startup, and IPC are excluded. Two full runs of the final code
passed all gates (388/392 directional agreements; the 4 disagreements
are near-parity noise only).

## Compilation and memory (separate from runtime)

| Metric | Value |
|---|---|
| Cold compile (`mojo build bench.mojo`, no prior artifact) | 2.8–2.9 s (page-cache variance, stated) |
| Executable size | 102072 bytes |
| Peak RSS, distance on `huge_ascii_random` (isolated child) | ~14.2–14.6 MB |

RSS includes process startup and the Mojo runtime; it is not
allocator-only. The frame itself is ~4 KB — RSS is dominated by
runtime, not input.

## 10. Known limitations

- C++ remains faster on every op (table above); the gaps are
  identified per-op and no universal-MoJo-faster claim is made.
- Sub-100-microsecond medians vary run to run; one workload in one run
  (`size_0064_random` distance) showed a shifted distribution (5.2 µs
  vs 3.3 µs elsewhere) attributed to environmental noise — directions
  and orders of magnitude are unaffected; read small magnitudes with
  their min/max bands.
- Page cache was warm for compilation; CPU frequency scaling was not
  pinned.
- Weighted distance and unpadded-hamming error paths are
  correctness-gated (goldens + live CLI probe) but not timed.
- No adversarial or pathological-input performance characterization.
- The Mojo-from-Python interop path from the methodology doc is not
  measured (`ctypes`/`PythonModuleBuilder` are out of project scope).
- `levenshtein_ratio` is marked `raises` (same convention as
  `myers_distance`): all in-repo callers already operate in `raises`
  contexts, and no behavioral difference results, but downstream
  non-`raises` callers would need `try`/propagation.

## 11. Future work

- Reduce per-call string conversion cost (shared code-point views or
  lazy conversion) — now the dominant term on trimmed-equal inputs.
- SIMD or lower-overhead iteration for hamming's inner loop.
- Denser Peq tables (e.g. small-alphabet fast path) to cut per-word
  `Dict` lookups in Myers/LCS.
- Timed weighted-distance benchmarks (currently gated, not timed).
- Evaluation of a banded/Ukkonen cutoff fast path (currently computed
  fully, then truncated).

## Reproduction

```bash
uv sync --extra dev
.venv/bin/python scripts/run_all_tests.py
.venv/bin/python libraries/levenshtein/benchmarks/run_benchmarks.py
```

Options: `--only a,b`, `--warmup N`, `--samples N` (>= 25), `--config`,
`--raw-out`. Raw samples plus metadata are written to
`build/levenshtein-bench.bench.json` (git-ignored). The driver deletes
the old binary before building, so the reported compile time is fresh
every run (page cache stays warm; this is stated, not hidden).
