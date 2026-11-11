# MessagePack Phase 2 results: integer codec

Phase 2 implements all ten MessagePack integer format families in native Mojo,
with exact-byte and bidirectional cross-language compatibility against
`msgpack==1.2.4`. Non-integer types remain out of scope.

## Files

Created:

- `libraries/msgpack/mojo/mojo_msgpack/integer.mojo` — canonical encoder,
  bounded decoder, error categories, and CLI integer transfer model.
- `libraries/msgpack/tests/mojo/test_integer_codec.mojo` — 12 native tests for
  exact bytes, boundaries, truncation, offsets, tags, and reader position.
- `libraries/msgpack/tests/python_compat/test_integer_compat.py` — 18 pytest
  cases for cross-language encoding/decoding and malformed input.
- `libraries/msgpack/PHASE2_RESULTS.md` — this report.

Modified:

- `mojo/mojo_msgpack/value.mojo` — added `VALUE_UINT`; `Value.unsigned` now
  keeps an unsigned tag.
- `mojo/cli.mojo` — integer `DECODE`/`ENCODE`; non-integer values remain
  `UNIMPLEMENTED`.
- `mojo/mojo_msgpack/__init__.mojo` — updated module description.
- `python_reference/generate_vectors.py` — unsigned integer model tag and 35
  integer boundary cases; schema version 1.1.0.
- `tests/mojo/vector_support.mojo` — `uint_from_decimal`.
- `tests/mojo/test_generated_vectors.mojo` — decodes and re-encodes every
  integer vector.
- `tests/vectors/msgpack_vectors.json` — 91 cases (35 integer).
- `tests/mojo/generated_vectors.mojo` — regenerated typed module.
- `shared/test_vectors/schema/msgpack_vectors.schema.json` — unsigned variant.
- `shared/validation/msgpack_vectors.py` — unsigned validation.
- `libraries/msgpack/README.md`, `README.md`, `docs/roadmap.md`,
  `libraries/msgpack/docs/batch_protocol.md` — status and protocol updates.

## Encoder summary

`encode_int` and `encode_uint` select the shortest valid representation in
big-endian order. `encode_value` accepts only `VALUE_INT`/`VALUE_UINT` and
rejects other kinds.

| Value range | Marker | Bytes after marker |
|-------------|--------|--------------------|
| `0..127` | positive fixint | none |
| `-1..-32` | negative fixint | none |
| `128..255` | `0xcc` uint8 | 1 |
| `256..65535` | `0xcd` uint16 | 2 |
| `65536..2^32-1` | `0xce` uint32 | 4 |
| `2^32..2^64-1` | `0xcf` uint64 | 8 |
| `-33..-128` | `0xd0` int8 | 1 |
| `-129..-32768` | `0xd1` int16 | 2 |
| `-32769..-2^31` | `0xd2` int32 | 4 |
| `-2^31-1..-2^63` | `0xd3` int64 | 8 |

Values are represented by `Int64` or `UInt64`, so out-of-range integers cannot
enter the API; no truncation or wrapping paths exist.

## Decoder summary

`IntegerDecoder` reads one marker, bounds-checks the full payload, then commits
the new position only after a complete successful decode. Failed decodes leave
`pos` unchanged. Positive fixint and `uint8/16/32/64` produce
`Value.unsigned`; negative fixint and `int8/16/32/64` produce `Value.integer`
with sign extension.

Errors carry a category and byte offset in the message:

- `truncated: offset N: ...`
- `unsupported-marker: offset N: ...`
- `trailing-data: offset N: ...`
- `invalid-model: offset N: ...`

`decode_exact` rejects trailing bytes. The CLI transfer model is 9 bytes:
`tag (0 signed, 1 unsigned) | uint64_be bits`.

## Boundary coverage

The 35 integer golden cases include every required value and immediate
neighbors at each transition:

- Positive: `0, 1, 126, 127, 128, 129, 254, 255, 256, 257, 65535, 65536,
  2^31-1, 2^31, 2^32-2, 2^32-1, 2^32, 2^63-1, 2^63, 2^64-1`.
- Negative: `-1, -31, -32, -33, -127, -128, -129, -32767, -32768, -32769,
  -(2^31-1), -2^31, -(2^31)-1, -(2^63-1), -2^63`.
- Markers covered by integer cases: positive/negative fixint, uint8/16/32/64,
  int8/16/32/64.
- Native exact-byte tables independently assert every encode boundary and all
  ten decode families.

## Cross-language compatibility

For all 35 integer vectors:

1. Python `msgpack.packb` → golden bytes: exact.
2. Python bytes → native `DECODE` → expected tag/value: exact.
3. Native `ENCODE` → golden bytes: exact.
4. Native bytes → Python `msgpack.unpackb` → expected integer: exact.

Additional checks cover equal signed/unsigned models for shared ranges,
negative roundtrips through both languages, truncated payloads for all eight
non-fixint integer markers, trailing bytes, unsupported markers, and malformed
transfer models.

## Test results

```text
$ .venv/bin/pytest -q
39 passed in 5.06s

$ ./build/test_depth
Summary [ 0.043 ] 8 tests run: 8 passed , 0 failed , 0 skipped

$ ./build/test_integer_codec
Summary [ 0.045 ] 12 tests run: 12 passed , 0 failed , 0 skipped

$ ./build/test_generated_vectors
Summary [ 11.785 ] 9 tests run: 9 passed , 0 failed , 0 skipped

$ .venv/bin/ruff check libraries shared scripts
All checks passed!

$ .venv/bin/ruff format --check libraries shared scripts
19 files already formatted

$ .venv/bin/python libraries/msgpack/python_reference/generate_vectors.py --check
vectors: 91 cases, committed artifacts are current
```

The 91-case bundle also validates against the published Draft 2020-12 schema
with `jsonschema.Draft202012Validator` (one-off check; not a project
dependency).

## Limitations

- Floats, strings, binary, arrays, maps, extensions, and timestamps still return
  `UNIMPLEMENTED` from the CLI.
- MessagePack has no signed/unsigned distinction for non-negative values. A
  signed `Value` containing a non-negative number decodes back with the
  unsigned tag; its bits and numeric value are preserved.
- The CLI integer model is only for integers and accepts exactly 9 bytes.
  A one-byte `0xc0` ENCODE payload retains the Phase 1 `UNIMPLEMENTED` response
  for compatibility; other malformed models return `ERROR`.
- Decode errors are textual (category plus offset), not a structured error
  object.
- `IntegerDecoder` owns a copy of its input; this is intentional for Phase 2,
  not a performance claim.
