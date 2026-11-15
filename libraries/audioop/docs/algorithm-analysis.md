# Algorithm analysis (from the pinned source)

Every rule here was read from `Modules/audioop.c` (CPython 3.12.3) and, where
observable, confirmed with `python_reference/probe_audioop.py`. Line-level
source excerpts are not reproduced; this is a behavioural specification for
the Mojo port.

## 0. Shared machinery

**Sample access.** Samples are read and written as native-order two's-
complement integers. The reference uses `GETINT8/16/24/32` and matching
setters, which assemble bytes with shifts (not `memcpy`), so a Mojo port can
do the same explicitly. 24-bit values sign-extend from bit 23.

**Validation.** `audioop_check_parameters(len, width)` =

1. `1 <= width <= 4` → else `Size should be 1, 2, 3 or 4`;
2. `len % width == 0` → else `not a whole number of frames`.

Functions taking two fragments additionally check equal lengths
(`Lengths should be the same`) or even lengths (`Strings should be even-sized`)
as appropriate. Order matters: width, then alignment, then function checks.

**32-bit domain.** `GETSAMPLE32` left-shifts samples to 32 bits
(`w1 << 24`, `w2 << 16`, `w3 << 8`, `w4` unchanged); `SETSAMPLE32` shifts
back. `ratecv` and ADPCM use this domain.

**Clamping helper.** `fbound(value)` clamps to `[minval, maxval]` using a
`minval + 1.0` guard, then applies `floor` and truncates to `int`. The guard
matters: with plain `< minval`, floating-point rounding at the negative
boundary could produce `minval - 1`.

## 1. Arithmetic

### `add(fragment1, fragment2, width)`

- Equal lengths required.
- Widths 1–3: per-sample `int a + int b`, then clamp.
- Width 4: per-sample addition in `double`, then clamp, specifically to avoid
  signed-int overflow (which is UB in C).
- Porting rule: accumulate in `Int64` (or double) and clamp; never rely on
  `Int32` wrap.

### `bias(fragment, width, bias)`

- `(sample + bias) & masks[width]`, reinterpreted as signed.
- This **wraps**, unlike `add`. Implement with `UInt32` masking.

### `mul(fragment, width, factor)`

- `fbound(sample * factor)` per sample.
- Rounding is floor-after-clamp, not nearest: `3 × 0.5 → 1`,
  `-3 × 0.5 → -2`.
- `nan`/`inf` factors: the reference reaches `(int)NaN`/`(int)Inf`, which is
  UB. The observed build yields zeros for widths 1–3 and `0x80000000` for
  width 4; the port defines its own policy and marks it undocumented.

### `tomono` / `tostereo`

- `tomono`: `fbound(lfactor*L + rfactor*R)` per frame.
- `tostereo`: `fbound(lfactor*S)` and `fbound(rfactor*S)` per input sample,
  interleaved. Overflow clamps per component, independently.

## 2. Statistics

| Function | Computation | Empty input |
| --- | --- | --- |
| `max` | max `abs(sample)`; `abs(-2^31)` computed in unsigned 32-bit → `2^31` | `0` |
| `minmax` | min and max signed sample | `(2^31-1, -2^31)` |
| `avg` | `sum / n` with C truncation toward zero | `0` |
| `rms` | `int(floor(sqrt(sum(s²)/n)))` in double | `0` |
| `avgpp` | sum of `abs(s[i]-s[i-1])` / `(n-1)`, truncating | `0` |
| `maxpp` | max `abs(s[i]-s[i-1])` | `0` |
| `cross` | count of sign transitions, with initial counter `-1` | `-1` |

Porting rules:

- Mojo `//` floors; use the truncating helper (`experiments/17_int_division`)
  for `avg` and `avgpp` to match C.
- `sum` in the reference is a C `int`; for width 4 and very large fragments
  this is signed-overflow UB. The port should accumulate in `Int64` and
  document that difference (defined behaviour, identical results wherever the
  reference is well-defined).
- `rms` must use `Float64` and `floor`, then convert; `sqrt` is IEEE-754 in
  both languages.
- `cross` compares `sample < 0` to the previous boolean, starting from `17`
  (any non-boolean), which is why the first non-empty sample always adds one
  to `-1`.

## 3. Matching (fixed 16-bit)

These three functions take no `width`, require even byte lengths, and read
native 16-bit samples.

### `findfactor(fragment, reference)`

```
F = sum(a[i]*r[i]) / sum(r[i]^2)
```

Requires equal lengths. Empty/empty → `0/0 = nan` (C double division).
This is a straight dot-product ratio; accumulate in `Float64` (or exact
`Float64`-safe integers) to match.

### `findfit(fragment, reference)`

- Requires `len(fragment) >= len(reference)` (`First sample should be
  longer`); equal lengths are **not** required.
- Computes, for each offset, `(Σr² · Σa² − (Σa·r)²) / Σa²`, and keeps the
  offset with the minimum residual; returns `(offset, factor)` where
  `factor = Σa·r / Σa²`.
- Sliding update: subtract the outgoing `a[j-1]²`, add the incoming
  `a[j+len2-1]²`; the cross-term is recomputed per window.
- Empty/empty → `(0, nan)`.

### `findmax(fragment, length)`

- `length` is in **samples** (the source divides the byte length by 2 first).
- `length < 0` or `length > frames` → `Input sample should be longer`
  (so a 4-byte fragment with `length=4` raises: frame count is 2).
- Sliding sum-of-squares; returns the offset of the largest window.

## 4. Fragments

### `getsample`

- Bounds-checked (`Index out of range`); returns a signed sample.

### `byteswap`

- Reverses the byte order inside each width-sized sample; width 1 is a no-op
  copy.

### `reverse`

- Reverses the **sample order** (`SETRAWSAMPLE(len - i - width)`), preserving
  each sample's internal byte order.

### `lin2lin(fragment, width, newwidth)`

- Output length `(len/width) * newwidth`.
- `width < newwidth`: `val <<= (newwidth - width)*8` (exact widening).
- `width > newwidth`: `val >>= (width - newwidth)*8`, arithmetic shift
  (truncates toward negative infinity), then store the low `newwidth` bytes.
- Width 4 narrowing operates on the signed 32-bit value; use `Int32`/`Int64`
  arithmetic shifts, not logical shifts.

## 5. Codecs

### u-law (`lin2ulaw` / `ulaw2lin`)

- Input samples are shifted to 14 bits (`>> 2`), clipped at `CLIP = 32635`,
  biased by `BIAS>>2 = 33`, segmented with `seg_uend` (8 thresholds),
  quantised to 4 bits, then XORed with `0xFF` (positive) or `0x7F`
  (negative) — u-law inverts all bits.
- Decode uses the 256-entry `_st_ulaw2linear16` table, then writes at the
  requested output width with the standard scaling.
- Constants: `BIAS 0x84`, `CLIP 32635`, `QUANT_MASK 0xF`, `SEG_SHIFT 4`.

### A-law (`lin2alaw` / `alaw2lin`)

- 13-bit domain; even-bit inversion: XOR `0xD5` for non-negative,
  `0x55` for negative (where the value becomes `-v - 1` before encoding).
- Segment search with `seg_aend` (8 thresholds); 4-bit quantisation; decode
  via the 256-entry `_st_alaw2linear16` table.

Both codec pairs are table-driven on decode and branch-exact on encode;
reproducing the segment tables is required for bit-identical output.

### Intel/DVI ADPCM (`lin2adpcm` / `adpcm2lin`)

- State `(valpred, index)` with `0 <= valpred < 0x8000`, `-0x8000 <= valpred`
  and `0 <= index < 89`; anything else → `bad state` (`ValueError`), while a
  non-tuple state is a `TypeError`.
- Predictor input is always the **16-bit** domain:
  `GETSAMPLE32(width) >> 16`.
- `step = stepsizeTable[index]` (89 entries); `indexTable` (16 entries:
  `-1,-1,-1,-1,2,4,6,8` twice).
- Encode: compute `diff`/sign, derive 3 magnitude bits (`delta`) by repeated
  halving of `step` (the source notes this is an approximation of
  `(delta+0.5)*step/4`), update `valpred`, clamp to `[-32768, 32767]`,
  update `index` and `step`.
- Packing: first sample in the **high nibble**, second in the low nibble;
  `len/(width*2)` output bytes; a trailing odd sample is dropped.
- Decode: first nibble is the high nibble; each input byte produces two
  samples; output length is `2 * len * width`; writes `valpred << 16` through
  `SETSAMPLE32`.
- `state=None` means `(0, 0)` on both sides.

### `ratecv(fragment, width, nchannels, inrate, outrate, state, weightA=1, weightB=0)`

- Validates width, `nchannels >= 1`, `weightA >= 1`, `weightB >= 0`, frame
  alignment (`not a whole number of frames`), and positive rates
  (`sampling rate not > 0`).
- Reduces `inrate/outrate` and `weightA/weightB` by their GCDs.
- State: `(d, ((prev, cur), ...))` with one pair per channel; `None` starts
  `d = -outrate` and all history zero.
- Loop: while `d < 0`, consume one input frame, shift history, and apply the
  digital filter
  `cur = (weightA*cur + weightB*prev) / (weightA + weightB)` (computed in
  double, truncated to `int`); `d += outrate`.
  While `d >= 0`, emit
  `out = (prev*d + cur*(outrate-d)) / outrate` (double, truncated to `int`);
  `d -= inrate`.
- All samples are promoted with `GETSAMPLE32` before filtering/interpolation
  and written back with `SETSAMPLE32`.
- Output buffer is allocated as `ceil(len/inrate) * outrate` frames and then
  trimmed to the bytes actually written; returned state's first element is
  the remaining `d`.
- Porting rules: same loop order, same double arithmetic, same truncation
  toward zero, and the same state layout so restarting mid-stream matches.

## 6. Porting hazard summary

| Hazard | Reference | Port requirement |
| --- | --- | --- |
| 32-bit `add` overflow | promoted to `double` | `Int64`/`Float64` accumulation |
| `bias` wrap vs `add` clamp | mask vs clamp | keep both behaviours distinct |
| `mul` rounding | `floor` after clamp with `minval+1.0` guard | copy exactly |
| `avg`/`avgpp` division | C truncation toward zero | trunc helper (Mojo `//` floors) |
| `abs(-2^31)` | unsigned 32-bit | avoid signed `abs` |
| `findfactor` empty | `nan` | propagate `nan`, no error |
| `findmax` length units | samples, fixed 16-bit | divide byte length by 2 |
| ADPCM domain | always 16-bit, independent of width | use `GETSAMPLE32 >> 16` |
| ADPCM nibble order | high nibble first | match packing |
| `ratecv` precision | double interpolation, int truncation | same order, same truncation |
| `ratecv` output length | over-allocate then trim | same trimming |
| native endianness | only byte order | little-endian default, explicit host check |
