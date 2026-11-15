# Peak analysis and fragment matching (Phase 4)

Five public audioop operations, implemented on the Phase 1 sample layer
(`mojo_audioop/peak_analysis.mojo`). Reference: CPython **3.12.3**
`Modules/audioop.c`.

## Implemented functions

| Function | Reference signature | Widths | Behaviour |
| --- | --- | --- | --- |
| `avgpp` | `avgpp(fragment, width)` | 1–4 | Truncated mean of unsigned peak-to-peak differences. |
| `maxpp` | `maxpp(fragment, width)` | 1–4 | Maximum unsigned peak-to-peak difference. |
| `findmax` | `findmax(fragment, length)` | fixed 16-bit | Sample index of the `length`-sample window with maximum energy. |
| `findfactor` | `findfactor(fragment, reference)` | fixed 16-bit | Least-squares factor `sum(a·r) / sum(r²)`. |
| `findfit` | `findfit(fragment, reference)` | fixed 16-bit | `(best_j, factor)` of the best-aligning window. |

## Peak detection (avgpp / maxpp)

Both functions share one walk. Per sample `i > 0`, only samples that
differ from the previous value are considered (`diff = val < prevval`).
The previous derivative direction starts at a sentinel (17), so the
**first observed direction is the baseline** and never produces a pair.
When the derivative changes sign, the previous value becomes the current
extreme; when a second extreme exists, the difference to it is recorded.
Consequences (all verified against the reference):

- `[1, 2, 3, 2, 1]` → **0** (a single peak never forms a pair).
- `[32767, -32768, 32767]` → **0** (same reason).
- `[1, 3, 1, 3]` → **2** (the middle reversal records the pair).
- Plateaus contribute nothing (equal samples are skipped).
- Fragments of at most one sample return 0 (`len <= width`).
- Empty → 0 (not an error).

Differences are computed in **32-bit unsigned arithmetic**
(`(unsigned)larger - (unsigned)smaller`, ordered by signed comparison),
so the `INT_MAX`/`INT_MIN` pair yields **4294967295** at width 4 —
`avgpp`/`maxpp` of `[MAX, MIN, MAX, MIN, MAX]` (w4) are 4294967295.
`avgpp` truncates `sum/nextreme` toward zero (`[0,3,0,1,0]` → 7/3 → 2);
`maxpp` keeps the maximum. Results may exceed the signed range and are
returned as `Int64`.

## Window search (findmax)

`findmax` has **no width argument**: the fragment is read as fixed
native-order int16 samples. `length` is measured in samples.
Validation: odd byte count → `Strings should be even-sized`; then
`length < 0 or len1 < length` → `Input sample should be longer`.

Energy starts as `sum(x[i]²)` for the first window and is updated with
the reference's exact expression `result = result + last² - first²`
(left-to-right double evaluation). Ties keep the **first** window
(strict `>`). `length` 0 is valid (constant zero energy → index 0);
an empty fragment with `length` 0 returns 0.

## Floating-point matching (findfactor / findfit)

Both are fixed 16-bit and require even-sized fragments
(`Strings should be even-sized`).

- `findfactor` additionally requires equal byte lengths
  (`Samples should be same size`) and returns `sum(a·r) / sum(r²)` as a
  double, accumulated by two separate sequential `sum += a[i] * r[i]`
  loops (reference `_sum2` order). A zero or empty reference divides 0
  by 0 → `nan` (IEEE-754, sign bit set: `0xfff8…` on this host, which
  the port reproduces bit-exactly).
- `findfit` requires the fragment to have at least as many samples as
  the reference (`First sample should be longer`). The initial window
  score is `(sum_ri_2·sum_aij_2 − sum_aij_ri²) / sum_aij_2`;
  `sum_aij_2` is updated incrementally
  (`sum_aij_2 = sum_aij_2 + last² − first²`), while `sum_aij_ri` is
  **recomputed fully** for every candidate (reference behaviour, and
  the source of its rounding quirks). Ties keep the first window
  (strict `<`); `nan` candidates (zero-energy windows) never beat a
  finite best. The factor is recomputed at the winning index and
  divided by `sum_ri_2`. Empty or all-zero inputs give `(0, nan)`.

## Validation and errors (verbatim)

- `Size should be 1, 2, 3 or 4` / `not a whole number of frames`
  (avgpp/maxpp, width-based)
- `Strings should be even-sized` (findmax/findfactor/findfit, odd bytes)
- `Input sample should be longer` (findmax)
- `Samples should be same size` (findfactor)
- `First sample should be longer` (findfit)

## CLI opcodes (test harness)

| Opcode | Request payload | Response payload |
| --- | --- | --- |
| `0x2E` avgpp | `uint8 width \| fragment` | ASCII decimal |
| `0x2F` maxpp | `uint8 width \| fragment` | ASCII decimal (may exceed signed 32-bit) |
| `0x30` findmax | `int64_be length \| fragment` | ASCII decimal sample index |
| `0x31` findfactor | `uint32_be len1 \| frag1 \| frag2` | 8 big-endian IEEE-754 bytes (bit-exact incl. nan) |
| `0x32` findfit | `uint32_be len1 \| frag1 \| frag2` | ASCII decimal index, space, 8 IEEE-754 bytes |

Note: `findmax` transmits no width byte because the reference API has
no width argument (fixed 16-bit). The payload format is documented here
as the deviation from the generic "width, length, fragment" sketch.

## Tests

- Native: `tests/mojo/test_peak_analysis.mojo` — 15 tests (peak walk,
  plateaus, truncation, unsigned wrap, tie-breaking, length semantics,
  fixed-16-bit interpretation, nan policy, validation, immutability).
- Python compatibility: `test_peak_analysis_cli.py` (11 framing tests,
  including bit-exact nan transport), `test_peak_analysis_oracle.py`
  (curated + randomized differential, seed `20260610`, bit-exact float
  comparison), `test_peak_analysis_vectors.py` (golden-vector replay).
- Golden vectors: 58 `p4-` cases (bundle now 243).

## Remaining unimplemented operations

`tomono`, `tostereo`, `ratecv`, `lin2alaw`, `alaw2lin`, `lin2ulaw`,
`ulaw2lin`, `lin2adpcm`, `adpcm2lin` (9 of 26).
