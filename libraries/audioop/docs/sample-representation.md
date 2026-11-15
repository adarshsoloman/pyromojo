# Sample representation (Phase 1)

Internal layer shared by every future audioop operation. It decodes and
encodes signed samples in native byte order and validates width and
fragment length. No public audioop function is implemented here.

## Supported widths

| Width | Bytes/sample | Signed range |
| ---: | ---: | --- |
| 1 | 1 | -128 … 127 |
| 2 | 2 | -32768 … 32767 |
| 3 | 3 | -8388608 … 8388607 |
| 4 | 4 | -2147483648 … 2147483647 |

Decoded values are returned as `Int32`; all four ranges fit. Encoding
accepts `Int64` so that values just outside the 32-bit range can be
detected and rejected instead of wrapping before validation.

## Native byte order

Fragments are raw native-endian bytes, exactly as the CPython 3.12
reference reads them through `GETSAMPLE*` (a direct native word load).
There is no endian argument in the frozen v0.1 API.

The port detects host order once per operation with:

```mojo
var one: UInt16 = 1
var bytes = bitcast[DType.uint8, 2](one)
```

This uses the supported `std.memory.bitcast` facility and no pointers.
`native_is_little_endian()` exposes the result; tests gate host-specific
byte expectations on it rather than assuming an endianness.

## 24-bit samples

24-bit values occupy three bytes and are sign-extended through a 32-bit
accumulator: the sign bit is bit 23, and negative values are formed as
`raw - 2^24`. Encoding masks to 24 bits and writes low, middle, high
bytes for little-endian hosts, reversed for big-endian hosts.
Boundaries `-8388608`, `-8388607`, `-1`, `0`, `1`, `8388606`, `8388607`
have dedicated native regression tests, including exact reference bytes.

## Validation

Validation order matches the reference (`audioop_check_size` before
`audioop_check_parameters`):

1. **Width** must be 1, 2, 3 or 4. Otherwise:
   `Size should be 1, 2, 3 or 4`.
2. **Fragment length** must be a multiple of the width. Otherwise:
   `not a whole number of frames`.
3. **Sample index** (single-sample decode) must be in range. Otherwise:
   `Index out of range`.

An **empty fragment is valid** and yields zero samples; it is never
reported as malformed. Trailing bytes that do not form a whole sample are
rejected, not dropped.

## Encoding values

There is no reference encoder, so out-of-range values have no upstream
exception to mirror. The port refuses to truncate or wrap:

`sample value <value> out of range for width <width>`

This includes values immediately beyond either end of each width's range,
which is why the encoder takes `Int64`. Fragment encoding validates every
value before writing, so a failure never returns partial output.

## Module responsibilities

`libraries/audioop/mojo/mojo_audioop/samples.mojo`:

- `native_is_little_endian`
- `validate_width`, `validate_fragment`
- `sample_min`, `sample_max`, `in_sample_range`, `validate_value`
- `decode_sample`, `decode_fragment`, `sample_count`
- `encode_sample`, `encode_fragment`

All byte access goes through one `_load_sample`/`_store_sample` pair; width
dispatch is closed over 1–4, so no duplication exists per width.

## CLI surface (test harness)

`libraries/audioop/mojo/cli.mojo` exposes the layer through the standard
PyroMojo framing:

- `0x20` decode: `uint8 width | fragment` → space-separated ASCII samples.
- `0x21` encode: `uint8 width | space-separated ASCII samples` → fragment.

Errors return `STATUS_ERROR` with the exact message text.

## Tests

- Native: `tests/mojo/test_samples.mojo` — widths, boundaries, round
  trips, fragment patterns, 24-bit regressions, invalid values, index
  errors, validation order, native order.
- Python compatibility: `tests/python_compat/` — framing, a curated
  differential suite, fixed-seed randomized differential cases, and the
  golden-vector cases. Decode Oracle: `audioop.getsample`; encode oracle:
  `int.to_bytes(width, sys.byteorder, signed=True)`, validated back
  through `getsample`.
- Vectors: 24 `sample_decode`/`sample_encode` cases added to the existing
  bundle (66 total), regenerable and `--check`-guarded.

## Limits

- Native order only; no endianness option (frozen scope).
- No buffer-protocol inputs; fragments are byte spans.
- No performance work or benchmarks in this phase.
