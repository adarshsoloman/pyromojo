# Sample statistics operations (Phase 3)

Six public audioop statistics functions, implemented on the Phase 1
sample layer (`mojo_audioop/statistics.mojo`). Reference: CPython
**3.12.3** `Modules/audioop.c`.

## Implemented functions

| Function | Reference signature | Widths | Behaviour |
| --- | --- | --- | --- |
| `getsample` | `getsample(fragment, width, index)` | 1–4 | Returns sample `index`; negative and out-of-range indices raise `Index out of range` (no Python-style negative indexing). |
| `max` | `max(fragment, width)` | 1–4 | Maximum **absolute** magnitude, computed in unsigned arithmetic: `abs(-2147483648) = 2147483648`. Empty → `0`. |
| `minmax` | `minmax(fragment, width)` | 1–4 | Signed `(minimum, maximum)` pair; empty → `(2147483647, -2147483648)`. |
| `avg` | `avg(fragment, width)` | 1–4 | Mean accumulated in `Float64`, then `floor`: `avg([-1, -2], 2) = -2`. Empty → `0`. |
| `rms` | `rms(fragment, width)` | 1–4 | `sqrt(sum(s²)/n)` accumulated in `Float64`, truncated toward zero (unsigned cast): `rms` of the 32-bit minimum is `2147483648`. Empty → `0`. |
| `cross` | `cross(fragment, width)` | 1–4 | Sign-class transitions where class = `sample < 0` (zero behaves like positive); counter starts at `-1` with a non-negative sentinel. Empty → `-1`; every non-empty fragment returns `>= 0`. |

## Verified CPython semantics

- **avg floors, it does not truncate.** The reference computes
  `(int)floor(sum / n)` in double: `[-1, -2] → -2`, `[-1, -2, -4] → -3`,
  `[1, 2, 4] → 2`. The Phase 0 algorithm-analysis note that said
  "truncation toward zero" was corrected by this phase's probe
  (`avg [-1,-2] w2 = -2`).
- **rms accumulates squares in double** and applies `(unsigned)sqrt(...)`
  — truncation via the cast. The port accumulates in `Float64` exactly
  like the reference, so rounding of large sums matches. `rms([2,-2,2,-3],
  2) = 2`; `rms([1,2], 2) = 1`.
- **max uses unsigned absolute values** (`(unsigned)-(int64)val`), so the
  result for a fragment containing the 32-bit minimum is `2147483648`,
  which exceeds the signed 32-bit range. The port returns this as
  `Int64`.
- **cross defines a crossing as a change of the boolean class**
  `sample < 0`. Zero is in the non-negative class, so `[1, 0, -1]` has
  exactly one transition and `[0, 1]` has zero. The `prevval = 17`
  sentinel makes the first sample always "transition" from the initial
  `-1` counter, which is why every non-empty fragment returns `>= 0`.
- **getsample** validates width and alignment first, then the index;
  an empty fragment has zero samples, so index 0 is out of range.

## Validation and errors (verbatim)

- `Size should be 1, 2, 3 or 4`
- `not a whole number of frames`
- `Index out of range` (`getsample` only; negative, `>= count`, and
  huge indices all produce it)

## CLI opcodes (test harness)

| Opcode | Request payload | Response payload |
| --- | --- | --- |
| `0x28` getsample | `uint8 width \| int64_be index \| fragment` | ASCII decimal sample |
| `0x29` max | `uint8 width \| fragment` | ASCII decimal (may exceed signed 32-bit) |
| `0x2A` minmax | `uint8 width \| fragment` | two ASCII decimals: `min max` |
| `0x2B` avg | `uint8 width \| fragment` | ASCII decimal |
| `0x2C` rms | `uint8 width \| fragment` | ASCII decimal (may exceed signed 32-bit) |
| `0x2D` cross | `uint8 width \| fragment` | ASCII decimal |

## Portability policy

No undefined behaviour is involved in these six operations; the port
reproduces the reference arithmetic directly (`Float64` accumulation for
`avg`/`rms`, unsigned-style magnitude for `max`). `rms` of an
astronomically long 32-bit fragment could overflow the reference's
double accumulator to infinity; the port behaves identically because it
uses the same accumulation.

## Tests

- Native: `tests/mojo/test_statistics.mojo` — 13 tests (all widths,
  boundaries, sentinels, floor/truncation evidence, sign classes,
  validation order, immutability).
- Python compatibility: `test_statistics_cli.py` (10 framing tests),
  `test_statistics_oracle.py` (curated + randomized differential, seed
  `20260610`), `test_statistics_vectors.py` (golden-vector replay).
- Golden vectors: 69 `p3-` cases (bundle now 185), including error
  cases for every operation, zero-heavy `cross`, floor evidence for
  `avg`, unsigned results for `max`/`rms`, and negative/out-of-range
  `getsample` indices.

## Remaining unimplemented operations

`avgpp`, `maxpp`, `findfactor`, `findfit`, `findmax`, `tomono`,
`tostereo`, `ratecv`, `lin2alaw`, `alaw2lin`, `lin2ulaw`, `ulaw2lin`,
`lin2adpcm`, `adpcm2lin` (14 of 26).
