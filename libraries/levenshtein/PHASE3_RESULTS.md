# Levenshtein Phase 3 results: targeted performance optimization

Phase 3 implements the three optimizations proposed in Phase 2,
each measured independently against the recorded Phase 2 baseline,
with correctness gates re-run at every step. No public API was added,
no reference semantics changed, and the DP oracle was not modified.

## 1. Original Phase 2 baseline

The baseline is `build/levenshtein-bench-phase3-baseline.bench.json`
(fresh full-suite run on the unmodified Phase 2 tree, same machine,
seed, and config: warmup 5, samples 25, naive cell budget 65536).
Headline standing before optimization (Mojo time / C++ time medians):

| Operation | Random content | Equal inputs |
|---|---|---|
| distance | 3–9x slower (e.g. 3.7x at `huge_ascii_random`) | 100–500x slower (519x at `huge_ascii_equal`) |
| ratio | ~200–250x slower at n≥256 | 18974x at `huge_ascii_equal` |
| hamming | 1.1x at n=12 growing to 36x at n=2048 | 27x at `huge_ascii_equal` |

Three gaps with identified causes: missing affix trimming (distance),
O(n·m) DP-LCS vs bit-parallel LCS (ratio), and per-call code-point
materialization (hamming).

## 2. Optimization A — common-prefix/suffix trimming (distance)

**What changed** (`mojo/mojo_levenshtein/distance.mojo`,
`_distance_codepoints` only): after code-point conversion, scan a
common prefix forward and a common suffix backward (never overlapping),
then dispatch the trimmed middle to the unchanged Myers/DP paths. When
nothing trims, the original lists are used with no copy, so random
content pays only the O(n) scan.

**Why it is exact.** For positive insertion/deletion/substitution
costs, an optimal alignment can always be transformed to match a
shared prefix and a shared suffix at zero cost, so stripping them
preserves the distance. This matches what the reference does
internally (`common_affix` removal, verified by behavior, not copied).

**Contract preserved.** The overflow/weight validation
(`_check_bounds`) runs on the *untrimmed* inputs before trimming, so
the Phase 1 guard keeps its documented meaning and its tested behavior
(`test_guards.test_weight_product_overflow_raises` initially caught
the naive placement and now passes).

## 3. Optimization B — blocked bit-parallel LCS (ratio)

**What changed** (new file
`mojo/mojo_levenshtein/algorithms/lcs.mojo`; `ratio.mojo` calls it
instead of `dp_lcs_length`): Hunt–Szymanski bit-vector LCS
(`U = S[c] | D; D = (D << 1) | 1; D = U & ~(U - D)`; answer is
`popcount(D)`), extended to arbitrary pattern lengths with one
`UInt64` word per 64 code points — multiword subtraction borrow,
cross-word shift carry with `1` injected at word 0, no shift ever
reaching the bit width (same guard discipline as `myers.mojo`).
High bits stay zero by construction (verified, not masked).

Implemented in two measured steps:

- **B1 — blocked LCS alone**, shorter input as pattern. Proves the
  algorithm independently of trimming.
- **B2 — plus affix trimming** in `levenshtein_ratio` (mirrored trim
  loop; full LCS = trimmed LCS + trimmed length; no-copy fast path
  when nothing trims, mirroring the distance dispatch). Trimming is
  exact for LCS for the same reason as for distance.

`dp_lcs_length` is untouched and remains the tested oracle.

## 4. Optimization C — materialization-free hamming

**What changed** (`mojo/mojo_levenshtein/hamming.mojo` only):
`levenshtein_hamming` no longer calls `to_codepoints`. Lengths come
from `len(s.codepoints())`, unequal lengths still raise the reference
message verbatim under `pad=False`, and the comparison is a single
lockstep pass with `zip(s1.codepoints(), s2.codepoints())` (verified
in a probe before use; `zip` stops at the shorter side, and the pad
difference is charged arithmetically). No temporary arrays.

## 5. Files created and modified

- Modified: `mojo/mojo_levenshtein/distance.mojo` (trim + dispatch
  split into `_dispatch`), `mojo/mojo_levenshtein/ratio.mojo`
  (bit-parallel LCS + trim, `raises` added — see §10),
  `mojo/mojo_levenshtein/hamming.mojo` (iterator comparison),
  `mojo/mojo_levenshtein/algorithms/__init__.mojo` (new export),
  `libraries/levenshtein/README.md` (status section).
- Created: `mojo/mojo_levenshtein/algorithms/lcs.mojo`,
  `tests/mojo/test_trimming.mojo` (10 tests),
  `tests/mojo/test_lcs_parity.mojo` (5 tests),
  `libraries/levenshtein/PHASE3_RESULTS.md` (this report).
- Not modified: `dynamic_programming.mojo`, `myers.mojo`,
  `unicode.mojo`, `protocol.mojo`, `cli.mojo`, all golden vectors,
  all benchmark harness files, MessagePack.

## 6. Correctness evidence

- New: 10 trimming tests (identical/long-prefix/long-suffix/both-ends/
  prefix-of-other/completely-different/repeated/unicode/weighted/
  cutoff/200-pair randomized production-vs-DP) — all pass.
- New: 5 LCS parity tests (fixed cases, word boundaries 60–70 /
  124–133 / 188–197, repeated/uniform to 300, 300 randomized ASCII +
  150 randomized code-point pairs vs `dp_lcs_length`, both argument
  orders) — all pass.
- Existing: all 25 prior native tests pass unchanged (8 distance,
  3 ratio, 4 hamming, 5 Myers parity, 1 golden-vector, 4 guards);
  24/24 Python compat tests pass; 434/434 golden vectors pass
  (bit-exact `Float64`, so the new ratio path is oracle-identical);
  both vector drift checks pass; `ruff check` and `ruff format
  --check` clean.
- Ratio float policy unchanged: exact `==` on packed `>d` bits in
  every benchmark correctness gate; no tolerances widened.

## 7. Before-and-after benchmark tables (medians, 25 samples)

Convention: `new / baseline` per workload; below 1.0 is faster.
"Baseline" is the fresh Phase 3 run of the unmodified tree.

### Distance (`levenshtein_distance`, production path)

| Workload | Baseline distance ns (min/max) | Optimized distance ns (min/max) | New/base |
|---|---|---|---|
| huge_ascii_equal 2048x2048 | 426734 (423087/455687) | 15218 (15168/15288) | 0.036 |
| huge_ascii_onesub 2048x2048 | 427455 (423808/442673) | 19066 (18965/25408) | 0.045 |
| huge_ascii_random 2048x2048 | 429910 (419861/868195) | 426962 (421572/444655) | 0.993 |
| medium_ascii_equal 64x64 | 3287 (3196/3577) | 551 (541/631) | 0.168 |
| medium_ascii_random 64x64 | 3236 (3176/3657) | 3297 (3256/5190) | 1.019 |
| long_ascii_random 256x256 | 12534 (12423/176699) | 12704 (12534/13045) | 1.014 |
| unequal_lengths 48x160 | 3807 (3737/4188) | 3827 (3707/4038) | 1.005 |
| repeated_uniform 128x128 | 3226 (3116/3547) | 3517 (3096/3607) | 1.090 |
| unicode_cjk 48x48 | 1983 (1954/2164) | 2024 (2003/2194) | 1.021 |
| emoji_astral 54x48 | 1924 (1913/2034) | 1963 (1934/2054) | 1.020 |
| combining 40x40 | 1372 (1343/166660) | 1383 (1343/1522) | 1.008 |
| size_0064_random 64x64 | 3176 (3125/3987) | 3336 (3246/28353) | 1.050 |
| size_2048_random 2048x2048 | 429990 (422676/595457) | 435507 (429116/693251) | 1.013 |
| short_ascii_random 12x12 | 681 (652/781) | 711 (691/791) | 1.044 |
| unequal_large 256x1024 | 36708 (36488/45004) | 37260 (36769/204163) | 1.015 |
| repeated_chars 128x128 | 3196 (3155/3727) | 3266 (3156/3597) | 1.022 |
| size_0031_random 31x31 | 1753 (1713/3346) | 1804 (1773/3516) | 1.029 |
| empty_vs_short 0x3 | 50 (40/90) | 60 (50/81) | 1.200 |

### Ratio (`levenshtein_ratio`, production path)

| Workload | Baseline ratio ns (min/max) | Optimized ratio ns (min/max) | New/base |
|---|---|---|---|
| huge_ascii_equal 2048x2048 | 16735767 (16285430/18192638) | 15179 (15158/20910) | 0.001 |
| huge_ascii_onesub 2048x2048 | 13451660 (13000581/16894663) | 18074 (18024/192722) | 0.001 |
| huge_ascii_random 2048x2048 | 17625952 (16513442/21361700) | 393849 (388449/403748) | 0.022 |
| medium_ascii_equal 64x64 | 12864 (12843/12894) | 551 (551/601) | 0.043 |
| medium_ascii_random 64x64 | 12584 (12573/12634) | 5170 (4749/12072) | 0.411 |
| long_ascii_random 256x256 | 249023 (247610/263390) | 11702 (11582/12173) | 0.047 |
| unequal_lengths 48x160 | 24055 (23914/262258) | 3447 (3346/3666) | 0.143 |
| repeated_uniform 128x128 | 48841 (48820/54020) | 2565 (2554/2675) | 0.053 |
| unicode_cjk 48x48 | 7514 (7494/19517) | 1924 (1893/2154) | 0.256 |
| emoji_astral 54x48 | 10339 (10329/10440) | 1854 (1803/1933) | 0.179 |
| combining 40x40 | 7104 (5119/8656) | 1302 (1282/1423) | 0.183 |
| size_0064_random 64x64 | 16290 (16251/32420) | 3256 (3136/3466) | 0.200 |
| size_2048_random 2048x2048 | 13868718 (13554834/16166033) | 398598 (395583/452269) | 0.029 |
| short_ascii_random 12x12 | 1011 (922/1263) | 651 (641/741) | 0.644 |
| unequal_large 256x1024 | 803885 (785932/1348849) | 33693 (33442/39253) | 0.042 |
| repeated_chars 128x128 | 47979 (47629/59099) | 2685 (2645/2786) | 0.056 |
| size_0031_random 31x31 | 3135 (3116/8987) | 1693 (1663/3326) | 0.540 |
| empty_vs_short 0x3 | 40 (40/70) | 60 (50/80) | 1.500 |

Stepwise attribution (mid-size subset): bit-parallel LCS alone (B1)
gives 0.022–0.25x on the workloads above; trimming (B2) adds the
identical-input collapse (huge equal: 392 µs → 15–18 µs, another
~22–25x) and is neutral elsewhere by construction (no-copy fast path).

### Hamming (`levenshtein_hamming`, production path)

| Workload | Baseline hamming ns (min/max) | Optimized hamming ns (min/max) | New/base |
|---|---|---|---|
| huge_ascii_equal 2048x2048 | 18494 (18434/190754) | 7904 (7884/8346) | 0.427 |
| huge_ascii_onesub 2048x2048 | 18514 (18464/25257) | 7834 (7794/8255) | 0.423 |
| huge_ascii_random 2048x2048 | 18805 (18734/23204) | 7824 (7794/8266) | 0.416 |
| medium_ascii_equal 64x64 | 642 (641/671) | 280 (270/301) | 0.436 |
| medium_ascii_random 64x64 | 631 (621/651) | 280 (270/350) | 0.444 |
| long_ascii_random 256x256 | 2325 (2324/2345) | 1002 (1001/1062) | 0.431 |
| unequal_lengths 48x160 | 902 (901/932) | 220 (210/241) | 0.244 |
| repeated_uniform 128x128 | 1213 (1212/7343) | 511 (501/541) | 0.421 |
| unicode_cjk 48x48 | 752 (751/801) | 360 (350/380) | 0.479 |
| emoji_astral 54x48 | 791 (781/811) | 361 (360/391) | 0.456 |
| combining 40x40 | 510 (491/521) | 250 (240/261) | 0.490 |
| size_0064_random 64x64 | 632 (631/652) | 280 (270/291) | 0.443 |
| size_2048_random 2048x2048 | 18484 (18445/52337) | 8085 (7885/8355) | 0.437 |
| short_ascii_random 12x12 | 160 (160/170) | 80 (70/90) | 0.500 |
| unequal_large 256x1024 | 5089 (5079/12022) | 1012 (1002/1072) | 0.199 |
| repeated_chars 128x128 | 1222 (1212/1233) | 511 (511/541) | 0.418 |
| size_0031_random 31x31 | 340 (330/351) | 220 (200/250) | 0.647 |
| empty_vs_short 0x3 | 50 (50/71) | 30 (30/50) | 0.600 |

## 8. Workloads that improved

- Distance: every workload with a shared affix — identical strings at
  any size (6x at 64×64, 22–28x at 2048×2048), near-identical strings
  (`huge_ascii_onesub` 22x, shared prefix+suffix cases), prefix-of-other
  pairs. Random content is unchanged (0.97–1.05x), as designed: a failed
  first-character comparison plus dispatch is the only added cost.
- Ratio: everything. Bit-parallel LCS gives 4–45x on general content
  (larger inputs win more: 0.200x at 64×64 → 0.022x at 2048×2048);
  trimming collapses identical inputs a further ~22–25x (392 µs →
  ~15–18 µs at 2048×2048). Even n=12 improves (0.64x): the word-level
  loop beats DP cell overhead at all sizes.
- Hamming: everything, uniformly 2–5x (0.199x–0.647x), including
  equal-length, padded-unequal, Unicode, and empty inputs. Removing
  two O(n) materializations dominates; the single lockstep pass is
  faster at every measured size.

## 9. Workloads that regressed

None beyond measurement noise. The largest apparent slowdowns are
`empty_vs_short` distance 1.20x (50→60 ns) and ratio 1.5x
(40→60 ns), `repeated_uniform` distance 1.09x, `size_0064_random`
distance 1.05x — all sub-100 ns absolute deltas or <10% on
microsecond-scale workloads, inside the documented run-to-run
variability (Phase 2 p90 ~30% at small sizes). Every regression
candidate was re-checked across the three full-suite runs; none
reproduces directionally.

## 10. Memory observations

- Executable size: 93144 → 102072 bytes (+9.6%, new LCS code).
- Peak RSS (isolated child, `huge_ascii_random` distance):
  14401536 B baseline → 14241792 B run 1 / 14561280 B run 2 (noise;
  no allocation-behavior change in the hot paths — trimming reuses or
  allocates trimmed lists of total size ≤ inputs, and hamming
  allocates nothing anymore).
- No new persistent state; peak temporary allocation is unchanged in
  scaling order (O(n) lists, O(words) vectors).

## 11. Known limitations

- `levenshtein_ratio` gained `raises` (same convention as
  `myers_distance`, required by `Dict` lookups in the Peq table). All
  in-repo callers (bench, CLI, tests) were already in `raises`
  contexts; no behavior changes, but the signature differs from Phase 1
  — recorded here deliberately rather than hidden.
- Equal-input Mojo/C++ gaps remain (distance 18.5x, ratio 17x at
  2048×2048): trimming removed the algorithmic gap; the remainder is
  per-call overhead (code-point conversion, List allocation, Peq
  build) against C++'s memcmp-fast-path. Reducing conversion cost is
  the next bottleneck, not algorithm choice.
- Ratio on random content is still 6–10x off C++ at n≥256: the
  remaining gap is per-word operation cost (Python-bigint-free but
  Dict-indexed Peq lookups per word per character), not complexity
  class — both sides are now O(n·m/w).
- Hamming is still ~14–15x off vectorized C++ at n=2048 (was 36x):
  per-element bounds-checked iteration vs SIMD. Further gains need
  lower-level iteration or SIMD, explicitly out of scope here.
- Weighted distance goes through the trimmed DP path (correctness-gated
  via goldens) but weighted workloads are not timed; the benchmark
  suite still covers unit weights only.
- Sub-100 ns medians carry wide bands; magnitudes there should be read
  with min/max, never as exact ranks. CPU frequency scaling was not
  pinned; page cache was warm.

## 12. Recommended future improvements

1. Reduce per-call string-conversion cost (shared code-point views or
   lazy conversion) — now the dominant term on trimmed-equal inputs.
2. SIMD or lower-overhead iteration for hamming's inner loop.
3. Denser Peq representation (e.g. small-alphabet fast path) to cut
   per-word Dict lookups in Myers/LCS.
4. Weighted-distance benchmark coverage (timed, not just gated).
5. A streaming/early-exit cutoff path for distance (currently computed
   fully, then truncated).

## Verification

Toolchain: Mojo 1.2.0 (2016d0cd), Python 3.13.14, pytest 9.2.0,
ruff 0.17.4, rapidfuzz 3.14.6, uv 0.12.5.

```text
$ uv sync --extra dev
Resolved 21 packages in 0.91ms
Checked 20 packages (no changes)

$ .venv/bin/python libraries/levenshtein/benchmarks/run_benchmarks.py \
    --raw-out build/levenshtein-bench-phase3-run1.bench.json
... (41 workloads, all checks passed)
cli validation probe: pad=False error frame correct
cold compile: 1.3 s, exe 102072 bytes
peak RSS on huge_ascii_random: distance 14241792 B

$ .venv/bin/python libraries/levenshtein/benchmarks/run_benchmarks.py \
    --raw-out build/levenshtein-bench-phase3-run2.bench.json
... (all checks passed; EXIT=0)
cold compile: 2.9 s, exe 102072 bytes
peak RSS on huge_ascii_random: distance 14561280 B

$ .venv/bin/python scripts/run_all_tests.py
run_all_tests: all suites passed

$ .venv/bin/python scripts/check_compatibility.py --library levenshtein
check_compatibility: all compatibility suites passed

$ .venv/bin/ruff check libraries shared scripts
All checks passed!

$ .venv/bin/ruff format --check libraries shared scripts
49 files already formatted
```

Three full benchmark runs (baseline + two post-optimization) all
passed every correctness gate (exact integers; bit-exact ratio
float64; identical hamming error text; live CLI error-frame probe).
Run 1 vs run 2 post-optimization: 386 agree, 6 disagree, all
near-parity noise (empty ties, short hamming/distance Mojo/C++ around
1–6x, ratio Mojo/py crossover). No Phase 1–2 test regressed: 153
pytest plus all 79 msgpack and 35 levenshtein native tests pass inside
`run_all_tests.py`.
