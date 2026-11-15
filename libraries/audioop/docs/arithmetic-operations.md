# Arithmetic and fragment operations (Phase 2)

The first six public audioop operations, implemented on the Phase 1
sample layer (`mojo_audioop/arithmetic.mojo`). Reference:
CPython **3.12.3** `Modules/audioop.c`.

## Implemented functions

| Function | Reference signature | Widths | Behaviour |
| --- | --- | --- | --- |
| `add` | `add(fragment1, fragment2, width)` | 1–4 | Per-sample sum, **saturating** (never wraps). Widths 1–3 clamp the integer sum; width 4 clamps an `Int64` sum. |
| `bias` | `bias(fragment, width, bias)` | 1–4 | `(sample + bias) & mask[width]`, reinterpreted signed — **wraps**, never clamps. |
| `mul` | `mul(fragment, width, factor)` | 1–4 | `fbound(sample * factor)`: clamp, then `floor`, then store. |
| `reverse` | `reverse(fragment, width)` | 1–4 | Reverses sample order; bytes inside each sample are unchanged. |
| `byteswap` | `byteswap(fragment, width)` | 1–4 | Reverses bytes inside each sample; sample order is unchanged. Width 1 is a copy. |
| `lin2lin` | `lin2lin(fragment, width, newwidth)` | 1–4 → 1–4 | Widening: left shift by `(newwidth-width)*8`. Narrowing: arithmetic right shift by `(width-newwidth)*8` (floor toward -inf). |

## Validation order (matches the reference)

1. Width of the primary fragment (`Size should be 1, 2, 3 or 4`).
2. Fragment alignment (`not a whole number of frames`).
3. Operation-specific checks.

- `add` validates fragment1 first, then requires equal lengths
  (`Lengths should be the same`); fragment2 is never independently
  misaligned when lengths are equal.
- `lin2lin` validates the source width before the destination width;
  both invalid reports the source-width message.
- `bias` rejects bias values outside the C `int` range
  (`Python int too large to convert to C int`) before fragment validation,
  matching the reference's argument conversion.
- An empty fragment is valid for every operation and yields an empty
  result.

## `mul` details

- The factor is an IEEE-754 double, transported bit-exactly through the
  CLI (`8-byte big-endian`) and the oracle.
- Rounding is floor-after-clamp, not round-to-nearest:
  `3 * 0.5 = 1`, `-3 * 0.5 = -2`, `-1 * 0.5 = -1`.
- `1000 * 0.001` is exactly `1.0` in IEEE-754, so it floors to `1`.
- `±inf` factors saturate through the defined clamp comparisons.
- **NaN deviation (documented).** The reference reaches `(int)NaN`
  (undefined; the observed build writes `INT_MIN`, truncating to `0` for
  widths 1–3). The port defines NaN results — from a NaN factor or from
  `0 * inf` — as **zero**, so behaviour is deterministic on every host.
  This follows the Phase 0 frozen decision that undefined float cases
  stay undefined and are excluded from equality assertions; the
  `mul-w2-nan` golden vector records the observed reference bytes and is
  excluded from replay.

## Error messages (verbatim)

- `Size should be 1, 2, 3 or 4`
- `not a whole number of frames`
- `Lengths should be the same` (`add` only)
- `Python int too large to convert to C int` (`bias` only, outside
  [-2147483648, 2147483647])

## CLI opcodes (test harness)

Framing and statuses are unchanged from Phase 1; new opcodes:

| Opcode | Request payload |
| --- | --- |
| `0x22` add | `uint8 width | uint32_be len1 | fragment1 | fragment2` |
| `0x23` bias | `uint8 width | int64_be bias | fragment` |
| `0x24` mul | `uint8 width | 8-byte IEEE-754 big-endian factor | fragment` |
| `0x25` reverse | `uint8 width | fragment` |
| `0x26` byteswap | `uint8 width | fragment` |
| `0x27` lin2lin | `uint8 width | uint8 newwidth | fragment` |

Request-shape errors (`add request too short: ...`, etc.) are error
frames; operation errors use the reference messages above.

## Tests

- Native: `tests/mojo/test_arithmetic.mojo` — 19 tests covering all six
  operations, boundaries, saturation vs wrap, floor rounding, empty
  fragments, invalid widths/lengths, validation order, all 16 `lin2lin`
  width pairs, and input immutability.
- Python compatibility: `tests/python_compat/test_arithmetic_cli.py`
  (framing), `test_arithmetic_oracle.py` (curated + fixed-seed
  randomized differential against CPython 3.12.3, seed `20260610`),
  `test_arithmetic_vectors.py` (golden-vector replay).
- Golden vectors: 50 `p2-` cases added (bundle now 116), including every
  valid `lin2lin` width pair, saturating/wrapping boundaries, inf
  factors, empty fragments, and the `add`/`bias` error paths.

## Limits

- No performance work; allocations are straightforward per operation.
- NaN factor/product policy is a documented deviation (see above).
- The other 20 public audioop operations remain unimplemented.
