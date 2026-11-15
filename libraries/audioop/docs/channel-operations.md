# Channel operations (Phase 5)

Two public audioop operations, implemented on the Phase 1 sample layer
(`mojo_audioop/channels.mojo`). Reference: CPython **3.12.3**
`Modules/audioop.c`.

## Implemented functions

| Function | Reference signature | Widths | Behaviour |
| --- | --- | --- | --- |
| `tomono` | `tomono(fragment, width, lfactor, rfactor)` | 1–4 | Mixes interleaved stereo pairs: `fbound(lfactor·left + rfactor·right)` per pair. |
| `tostereo` | `tostereo(fragment, width, lfactor, rfactor)` | 1–4 | Expands each mono sample to `(fbound(value·lfactor), fbound(value·rfactor))`, stored left first. |

## Arithmetic (shared `fbound` with `mul`)

Both operations compute in IEEE-754 double precision and convert through
the reference's `fbound`: clamp (`> max → max`; `< min+1.0 → min`), then
`floor`, then integer conversion. This is floor, not round-to-nearest:
`tomono([1,-2], 2, 0.5, 0.5) = -1`; `tostereo([3], 2, 0.5, 0.5) = 1`;
`tostereo([-3], 2, 0.5, 0.5) = -2`. Results saturate at the signed
sample limits — never wrap.

- `tomono` accumulation order matches the reference:
  `lfactor·left + rfactor·right` evaluated left-to-right.
- `tostereo` evaluates `value·lfactor` and `value·rfactor` separately,
  each through its own `fbound`.
- `±inf` factors saturate through the defined clamp comparisons.
- **NaN deviation (documented, same policy as `mul`):** NaN results —
  from a NaN factor or from `inf·0 + (−inf)·x` style cancellation —
  are defined as **zero** in the port. At widths 1–3 this matches the
  reference's observed behaviour exactly (the reference's `(int)NaN =
  INT_MIN` truncates to zero in the low bytes); at width 4 the
  reference writes `INT_MIN` where the port writes `0`, a documented
  deviation excluded from equality assertions
  (`test_w4_nan_undefined`).

## Sample ordering

- `tomono` input is interleaved `(left, right)` pairs; output is one
  mono sample per pair. Sample count must be **even**: a single sample
  or odd count raises `not a whole number of frames` (after the usual
  width/alignment validation of the fragment). Empty → empty.
- `tostereo` input is mono; output is interleaved
  `(left, right)` per input sample, left first. Any alignment is
  accepted; empty → empty.

## Validation and errors (verbatim)

- `Size should be 1, 2, 3 or 4`
- `not a whole number of frames` (fragment alignment for both;
  stereo-frame alignment for `tomono`)

## CLI opcodes (test harness)

| Opcode | Request payload | Response payload |
| --- | --- | --- |
| `0x33` tomono | `uint8 width \| 8-byte IEEE-754 BE lfactor \| 8-byte IEEE-754 BE rfactor \| fragment` | mono fragment bytes |
| `0x34` tostereo | same payload format | stereo fragment bytes |

The factor transport is identical to `mul` (`0x24`), so NaN and
infinities survive bit-exactly.

## Tests

- Native: `tests/mojo/test_channels.mojo` — 11 tests (mixing order,
  saturation at all widths, floor rounding, factor coverage, alignment
  and width errors, NaN policy, immutability).
- Python compatibility: `test_channels_cli.py` (10 framing tests,
  including bit-exact factor transport), `test_channels_oracle.py`
  (curated + randomized differential, seed `20260610`), and
  `test_channels_vectors.py` (golden-vector replay).
- Golden vectors: 33 `p5-` cases (bundle now 276), including empty
  fragments, single samples, odd counts, boundary samples at all
  widths, zero/fractional/large/infinite/NaN factors, and the width-4
  NaN record.

## Remaining unimplemented operations

`ratecv`, `lin2alaw`, `alaw2lin`, `lin2ulaw`, `ulaw2lin`, `lin2adpcm`,
`adpcm2lin` (7 of 26).
