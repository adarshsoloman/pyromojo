# MessagePack Phase 3 results: float, string, and binary codecs

Phase 3 adds native Mojo encoding and decoding for Float32, Float64, strings,
and binary values. Arrays, maps, extensions, timestamps, nil, and bool remain
unimplemented.

## Files

Created:

- `libraries/msgpack/mojo/mojo_msgpack/scalar.mojo` — float, string, and
  binary wire codecs; scalar dispatch; CLI scalar transfer models.
- `libraries/msgpack/tests/mojo/test_scalar_codec.mojo` — 13 native tests for
  exact bits, marker boundaries, UTF-8 validation, binary preservation, and
  malformed input.
- `libraries/msgpack/tests/python_compat/test_scalar_compat.py` — 33 pytest
  cases for bidirectional cross-language compatibility and error behaviour.
- `libraries/msgpack/PHASE3_RESULTS.md` — this report.

Modified:

- `mojo/cli.mojo` — scalar `DECODE`/`ENCODE`; containers still return
  `UNIMPLEMENTED`.
- `mojo/mojo_msgpack/integer.mojo` — documented signed-positive decoding.
- `mojo/mojo_msgpack/__init__.mojo` — updated module description.
- `python_reference/generate_vectors.py` — Float32/Float64, string, binary,
  and malformed scalar cases; `pack_model` supports `use_single_float`.
- `tests/mojo/generated_vectors.mojo` — regenerated 127-case module.
- `tests/mojo/test_generated_vectors.mojo` — decodes and re-encodes all 80
  supported scalar golden cases.
- `tests/python_compat/test_vectors.py` — reference replay uses the generator's
  `pack_model` so Float32 vectors exercise `use_single_float`.
- `tests/vectors/msgpack_vectors.json` — expanded to 127 cases.
- `shared/test_vectors/schema/msgpack_vectors.schema.json` — schema 1.2.0.
- `shared/validation/msgpack_vectors.py` — schema/generator 1.2.0.
- `libraries/msgpack/docs/batch_protocol.md` — scalar models and statuses.
- `libraries/msgpack/README.md`, `README.md`, `docs/roadmap.md` — status and
  compatibility notes.

## Implemented format families

| Category | Markers |
|----------|---------|
| Float32 | `ca` |
| Float64 | `cb` |
| String | fixstr (`a0`-`bf`), str8 (`d9`), str16 (`da`), str32 (`db`) |
| Binary | bin8 (`c4`), bin16 (`c5`), bin32 (`c6`) |

Floats are stored and emitted as raw IEEE 754 bit patterns. Strings are
validated as UTF-8 during decoding and encoded from UTF-8 bytes. Binary payloads
are copied exactly without text interpretation. Marker selection uses payload
byte length, not character count.

Reserved marker `c1` is distinguished from valid but unsupported categories:
it returns `ERROR` as `invalid-marker`, while nil, bool, containers, extensions,
and timestamps remain `UNIMPLEMENTED`.

## Boundary test coverage

Floats:

- Float64: positive and negative zero, 1.5, a negative normal, max finite, min
  normal, min subnormal, negative subnormal, positive and negative infinity,
  quiet NaN payload, signaling NaN payload, and negative NaN payload.
- Float32: positive and negative zero, 1.0, 1.5, -1.5, max finite, min normal,
  min subnormal, negative subnormal, positive and negative infinity, quiet NaN
  payload, and negative NaN payload.
- Float32 roundtrips through Python use `msgpack.packb(..., use_single_float=True)`;
  default Python packing only emits Float64.
- Truncated Float32/Float64 payloads and trailing bytes are rejected with a
  category and offset.

Strings:

- Empty, ASCII, multibyte Unicode, and embedded NUL.
- Byte-length boundaries: 31/32, 255/256, and 65,535/65,536.
- Multibyte cases where 31 and 32 UTF-8 bytes correspond to 11 and 16
  characters, proving marker selection is byte-based.
- Truncated fixstr, str8, str16, and str32 payloads; a str32 header declaring
  `0xffffffff` bytes is rejected before allocation.
- Invalid UTF-8: lone continuation, overlong encoding, surrogate, above
  U+10FFFF, and a complete payload ending inside a multibyte sequence.
- Trailing bytes after a complete string are rejected.

Binary:

- Empty payload, embedded NUL, all byte values `0x00` through `0xff`, and
  non-UTF-8 data.
- Byte-length boundaries: 255/256 and 65,535/65,536.
- Truncated bin8, bin16, and bin32 payloads; a bin32 header declaring
  `0xffffffff` bytes is rejected before allocation.
- Trailing bytes after a complete binary payload are rejected.

The bundle now contains 127 cases: 35 integer, 26 float, 12 string, 7 binary, 8
extension, 6 map, 6 timestamp, 5 array, 2 bool, 1 nil, and 19 error cases.

## Cross-language compatibility

For all 45 Phase 3 golden cases (26 float, 12 string, 7 binary):

1. Python encodes the model and matches the golden bytes.
2. Mojo `DECODE` returns the expected scalar model and bits/text/bytes.
3. Mojo `ENCODE` matches the golden bytes.
4. Python decodes the result to the expected value or exact Float32/Float64
   bits.

Float32 compatibility is checked separately with
`msgpack.packb(value, use_single_float=True)`. Default Python Float64 output is
checked for every Float64 case. Malformed string, binary, and float inputs are
also exercised through the CLI.

Signed-positive integer behavior is documented in the library README, batch
protocol, and integer module: MessagePack does not preserve an independent
signedness distinction for non-negative wire values, so positive fixint and
uint8/16/32/64 decode with the unsigned tag.

## Test results

```text
$ .venv/bin/pytest -q
72 passed in 8.75s

$ ./build/test_depth
Summary [ 0.055 ] 8 tests run: 8 passed , 0 failed , 0 skipped

$ ./build/test_integer_codec
Summary [ 0.036 ] 12 tests run: 12 passed , 0 failed , 0 skipped

$ ./build/test_generated_vectors
Summary [ 15.045 ] 10 tests run: 10 passed , 0 failed , 0 skipped

$ ./build/test_scalar_codec
Summary [ 0.468 ] 13 tests run: 13 passed , 0 failed , 0 skipped

$ .venv/bin/ruff check libraries shared scripts
All checks passed!

$ .venv/bin/ruff format --check libraries shared scripts
21 files already formatted

$ .venv/bin/python libraries/msgpack/python_reference/generate_vectors.py --check
vectors: 127 cases, committed artifacts are current
```

The bundle and schema also validate under JSON Schema Draft 2020-12 with
`jsonschema.Draft202012Validator` (one-off check; not a project dependency).

## Remaining limitations

- Arrays, maps, extensions, timestamps, nil, and bool still return
  `UNIMPLEMENTED` from the CLI.
- Python's default encoder cannot emit Float32; Float32 compatibility uses the
  explicit `use_single_float=True` path.
- Python canonicalizes a signaling Float32 NaN while packing (sets the quiet
  bit). Mojo preserves the exact signaling payload natively; the golden Float32
  set therefore uses quiet NaN payloads, while native tests cover signaling
  bits. Float64 signaling NaN payloads are preserved by both sides.
- The CLI integer model remains exactly 9 bytes. Float32, Float64, string, and
  binary models use tags `0x10` through `0x13`; unknown tags are `ERROR`.
- A one-byte `0xc0` ENCODE payload retains the Phase 1 `UNIMPLEMENTED` response.
- Decode errors are textual (category plus offset), not a structured error
  object.
- String decoding validates and copies the payload; binary decoding copies it.
  No performance optimization or zero-copy path is claimed in this phase.
