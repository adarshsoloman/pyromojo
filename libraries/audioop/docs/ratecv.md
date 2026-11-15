# Stateful sample-rate conversion (`ratecv`, Phase 6)

Port of CPython 3.12.3 `audioop.ratecv` (`Modules/audioop.c`,
`audioop_ratecv_impl`), implemented in `mojo_audioop/ratecv.mojo`.

## Signature

```python
ratecv(fragment, width, nchannels, inrate, outrate, state=None,
       weightA=1, weightB=0) -> (bytes, (d, ((prev_i, cur_i) per channel)))
```

Mojo API: `ratecv(...)` starts with a fresh state (reference
`state=None`); `ratecv_continue(..., state: RatecvState, ...)` resumes
from a previously returned state. `RatecvState` holds the phase
accumulator `d` and per-channel `prev_i`/`cur_i` filter history; the
values are the 32-bit-scaled samples described below.

## CPython algorithm (exact)

1. **Validation order.** First the C `int` argument conversion of
   `nchannels`, `inrate`, `outrate`, `weightA`, `weightB`
   (`Python int too large to convert to C int`, taking precedence over
   every body check), then:
   - width 1–4 (`Size should be 1, 2, 3 or 4`),
   - `nchannels >= 1` (`# of channels should be >= 1`),
   - `width <= INT_MAX / nchannels`
     (`width * nchannels too big for a C int`),
   - `weightA >= 1 and weightB >= 0`
     (`weightA should be >= 1, weightB should be >= 0`),
   - fragment length a multiple of `width*nchannels`
     (`not a whole number of frames`) — **checked before the rates**,
   - `inrate > 0 and outrate > 0` (`sampling rate not > 0`).
2. **Reduction.** `inrate`/`outrate` and `weightA`/`weightB` are divided
   by their greatest common divisors. `gcd(w, 0) = w`, so `(5, 0)`
   reduces to `(1, 0)`.
3. **Scaling.** Samples are read/written at the 32-bit position exactly
   like the reference's `GETSAMPLE32`/`SETSAMPLE32`: value multiplied by
   `2^(32 - 8*width)` (w1 ×2²⁴, w2 ×2¹⁶, w3 ×2⁸, w4 ×1). All filter and
   interpolation arithmetic happens at this scale; output samples are
   stored through the top-aligned truncating shift.
4. **Filter recurrence.** Per consumed frame, per channel:
   `prev_i <- cur_i; cur_i <- (int)((weightA*raw + weightB*prev_i) /
   (weightA+weightB))` evaluated in IEEE-754 double and truncated
   **toward zero** (C `(int)` cast — distinct from `fbound`'s floor).
5. **Phase loop.** `d` starts at `-outrate` (after reduction) for a
   fresh state. Input is consumed only while `d < 0` (each frame adds
   `outrate`); output is produced only while `d >= 0` (each output
   frame subtracts `inrate`, per channel
   `(int)((prev_i*d + cur_i*(outrate-d)) / outrate)` in double,
   truncated toward zero). When the input is exhausted during the
   `d < 0` phase, the call returns the output so far and the state.
   Output for a fragment is whatever was produced before the input ran
   out — e.g. 5 frames at 16k→8k yield 3 output frames.
6. **State.** Returned as `(bytes, (d, ((prev_i, cur_i) per channel)))`.
   An empty fragment returns `(b"", (-outrate, zeros))` for a fresh
   state and leaves a continued state untouched except that `d` is
   returned unchanged. State depends on the reduced rates/weights and
   the channel count; it can be fed back into the next call.

## Chunk equivalence (verified)

Because input is consumed only in the `d < 0` phase and output is
produced only in the `d >= 0` phase, processing is exactly
chunk-composable: splitting a fragment in any chunk sizes (equal,
unequal, one-sample, with empty chunks in between) and feeding the
returned state forward produces byte-identical output and an identical
final state. Verified against the reference and the port for mono and
multichannel, up- and downsampling, and non-integer ratios
(`test_chunk_equivalence_reference_and_port`,
`test_ratecv_chunk_equivalence*`).

## Port policies

- No undefined behaviour is involved; the double-precision
  accumulation and C `(int)` truncation-toward-zero are reproduced
  exactly (`Int64(Float64)` truncates toward zero in Mojo as in C).
- `d` and the per-channel values are `Int64`; the reference uses C
  `int`. Argument-range validation reproduces the C `int` conversion
  errors; `d` itself stays in the same bounded range
  (`|d| < inrate + outrate` after reduction), so 32-bit `int` overflow
  cannot occur for valid arguments.
- The Mojo API splits `state=None` into `ratecv` (fresh) and
  `ratecv_continue` (resumed); the CLI carries the state explicitly.

## CLI opcode `0x35`

Request:
`uint8 width | int64_be nchannels | int64_be inrate | int64_be outrate |
int64_be weightA | int64_be weightB | uint8 has_state |
[int64_be d | nchannels × (int64_be prev | int64_be cur)] | fragment`.
The channel count is 8 bytes so argument-conversion errors stay
reachable through the CLI.

Response: `uint32_be out_len | output bytes | int64_be d |
nchannels × (int64_be prev | int64_be cur)` — the state block can be
pasted into the next request.

## Known limits

- `state` validation differences: the reference rejects a non-tuple
  state with `TypeError` and a wrong channel count with
  `ratecv(): illegal state argument`; the CLI state block is checked
  structurally ("ratecv request too short: need the full state") and
  the port API takes the channel count from the call. JSON round-trips
  require converting lists back to tuples (the oracle does this).
- No benchmarks or performance work in this phase.
