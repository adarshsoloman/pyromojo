# MessagePack Phase 5 results: extensions and timestamps

Phase 5 adds native Mojo encoding and decoding for all eight MessagePack
extension families and the standard timestamp extension (type `-1`), working
as top-level values, inside arrays and maps, and as map keys. All Phase 1-4
behavior is preserved; bare top-level nil and bool keep their Phase 1
`UNIMPLEMENTED` response.

## Files

Created:

- `libraries/msgpack/mojo/mojo_msgpack/extension.mojo` — ext/timestamp wire
  codecs, timestamp selection and validation, CLI transfer models.
- `libraries/msgpack/tests/mojo/test_extension_codec.mojo` — 11 native tests
  for exact bytes, marker boundaries, timestamp selection, invalid timestamps,
  truncated extensions, nesting, and model roundtrips.
- `libraries/msgpack/tests/mojo/test_regressions.mojo` — 8 cross-phase
  regression pins for integer boundaries, float bits, UTF-8 validation,
  binary preservation, recursion/depth limits, duplicate keys, error
  categories, scalar API stability, and model tags.
- `libraries/msgpack/tests/python_compat/test_extension_compat.py` — 26
  pytest cases for `Timestamp` semantics, datetime packing, C/fallback
  decoder parity, error behaviour, and the negative-code deviation.
- `libraries/msgpack/PHASE5_RESULTS.md` — this report.

Modified:

- `mojo/mojo_msgpack/container.mojo` — dispatches ext/timestamp markers and
  model tags (`0x16`/`0x17`) to the extension codec.
- `mojo/cli.mojo` — docstring updated; `DECODE`/`ENCODE` now cover extensions
  and timestamps with no protocol change.
- `python_reference/generate_vectors.py` — schema/generator 1.4.0, extension
  and timestamp boundary/nested/error cases.
- `tests/mojo/generated_vectors.mojo` — regenerated 162-case module.
- `tests/mojo/test_generated_vectors.mojo` — decodes and re-encodes all 19
  array/map and all 24 ext/timestamp golden cases.
- `tests/mojo/test_container_codec.mojo` — one expectation updated: an ext8
  child inside a short array is now a decoded child plus truncation, not
  `unsupported-marker`.
- `tests/python_compat/test_container_compat.py` — model builders extended
  with `0x16`/`0x17`; obsolete all-unimplemented test replaced by positive
  coverage; golden counts updated for the new nested cases.
- `tests/vectors/msgpack_vectors.json` — expanded to 162 cases.
- `shared/test_vectors/schema/msgpack_vectors.schema.json` — schema 1.4.0;
  ext code range widened to -128..127.
- `shared/validation/msgpack_vectors.py` — schema/generator 1.4.0; ext code
  range widened to -128..127.
- `libraries/msgpack/docs/batch_protocol.md` — ext/timestamp models,
  selection rules, and Python reference differences.
- `libraries/msgpack/README.md`, `README.md`, `docs/roadmap.md` — status and
  compatibility notes.

## Implemented extension formats

| Family | Marker | Payload |
|--------|--------|---------|
| FixExt1/2/4/8/16 | `d4`-`d8` | 1/2/4/8/16 bytes |
| Ext8 | `c7` | u8 length |
| Ext16 | `c8` | u16 big-endian length |
| Ext32 | `c9` | u32 big-endian length |

Encoding selects the shortest marker: lengths 1, 2, 4, 8, and 16 use the
fixed families; every other length (including empty payloads) uses
ext8/ext16/ext32 by size. Type codes are signed 8-bit values preserved
exactly. Lengths are validated against the remaining input before any
allocation, so a declared 4-billion-byte payload costs one `truncated` error.

## Timestamp32/64/96 semantics

Timestamps are extension type `-1` with big-endian packing:

- Timestamp32: 4-byte unsigned seconds, nanoseconds zero.
- Timestamp64: 8-byte `(nanoseconds << 34) | seconds`.
- Timestamp96: 4-byte unsigned nanoseconds plus 8-byte signed seconds.

Selection matches the reference exactly: zero nanoseconds with seconds fitting
in 32 bits uses timestamp32; seconds below 2^34 use timestamp64; everything
else — including all negative seconds — uses timestamp96. Encoding validates
nanoseconds against 0..999999999; decoding validates the 64- and 96-bit
nanosecond fields the same way. A type `-1` payload with a length outside
{4, 8, 12} or out-of-range nanoseconds fails with `invalid-timestamp` (at the
marker offset) and is never reinterpreted as a generic extension — including
through the CLI model path, where code `-1` models must also decode to valid
timestamps.

## Python reference compatibility decisions

Probed against the pinned `msgpack==1.2.4` before choosing semantics:

- `Timestamp(seconds, nanoseconds)` validates nanoseconds (0..999999999
  inclusive); fields, `to_unix`/`to_unix_nano`/`from_unix`, equality, and
  hashing are covered by tests.
- `unpackb(timestamp=N)`: 0 returns `Timestamp`, 1 returns float seconds, 2
  returns total-nanoseconds int, 3 returns an aware UTC datetime. All four are
  tested against both the C and fallback decoders.
- Datetimes pack only with `datetime=True`, must be timezone-aware, are
  normalized to UTC, and scale microseconds to nanoseconds. Naive datetimes
  raise `ValueError`; packing without the flag raises `TypeError`.
- `ExtType` codes are restricted to 0..127, and wire-negative codes raise
  `ValueError: code must be 0~127` on decode. The native codec intentionally
  accepts the full signed int8 range (documented deviation, pinned by a test
  asserting both sides: reference rejects, native roundtrips `d4fe2a`).
- The reference never reinterprets bad timestamp payloads as generic
  extensions (`invalid timestamp data`); the native `invalid-timestamp`
  mirrors this without sharing message text.

## Recursive integration

Extensions and timestamps decode and encode as top-level values, as array
items, as map keys and values, and through the recursive CLI models
(`0x16` ext, `0x17` timestamp; existing tags unchanged). Golden vectors pin
an array mixing an ext8, a timestamp64, and nil, plus a map with a timestamp32
key and a fixext1 value. Bare top-level nil/bool still report
`UNIMPLEMENTED`; code `-1` in an ext model is validated as a timestamp.

## Malformed-input handling

- Truncated fixext/ext8/ext16/ext32 headers, type bytes, and payloads report
  `truncated` with the marker offset; `ext32` huge declarations fail before
  allocation.
- Trailing bytes after a complete value report `trailing-data`.
- `0xc1` stays `invalid-marker`; `decode_scalar_exact` still reports
  `unsupported-marker` for containers, preserving the scalar API.
- Timestamp length and nanosecond violations report `invalid-timestamp`;
  ext/timestamp models validate lengths, framing, and nanoseconds before
  constructing values.

The bundle now contains 162 cases: 35 integer, 26 float, 12 string, 7 binary,
9 array, 10 map, 14 ext, 10 timestamp, 2 bool, 1 nil, and 36 error cases
(27 old plus negative ext code, 4 truncated ext, and 4 timestamp violations).

## Test results

```text
$ .venv/bin/pytest -q
116 passed in 9.47s

$ ./build/test_depth
Summary [ 0.034 ] 8 tests run: 8 passed , 0 failed , 0 skipped

$ ./build/test_integer_codec
Summary [ 0.039 ] 12 tests run: 12 passed , 0 failed , 0 skipped

$ ./build/test_generated_vectors
Summary [ 46.461 ] 12 tests run: 12 passed , 0 failed , 0 skipped

$ ./build/test_scalar_codec
Summary [ 0.473 ] 13 tests run: 13 passed , 0 failed , 0 skipped

$ ./build/test_container_codec
Summary [ 14.271 ] 13 tests run: 13 passed , 0 failed , 0 skipped

$ ./build/test_extension_codec
Summary [ 0.259 ] 11 tests run: 11 passed , 0 failed , 0 skipped

$ ./build/test_regressions
Summary [ 0.045 ] 8 tests run: 8 passed , 0 failed , 0 skipped

$ .venv/bin/ruff check libraries shared scripts
All checks passed!

$ .venv/bin/ruff format --check libraries shared scripts
24 files already formatted

$ .venv/bin/python libraries/msgpack/python_reference/generate_vectors.py --check
vectors: 162 cases, committed artifacts are current
```

The bundle and schema also validate under the stdlib validator
(`test_bundle_is_structurally_valid`); the JSON Schema Draft 2020-12
one-off check needs the optional `jsonschema` package, which is not
installed in this environment.

## Remaining limitations

- Bare top-level nil and bool models keep the Phase 1 `UNIMPLEMENTED`
  response; nested nil/bool are fully supported.
- Wire-negative extension codes (other than the validated timestamp path)
  decode natively but are rejected by the reference; the deviation is pinned
  by `error_negative_ext_code` and the native negative-code tests.
- The native default depth limit is 128; the reference accepts up to 1024.
- The reference caps declared container/ext sizes against the input buffer;
  the native side reports `container-limit`/`truncated` against its own caps.
  Both reject.
- Python's default mapping type collapses duplicate keys and forbids
  unhashable keys; ordered/duplicate semantics exist only through
  `object_pairs_hook` and the native model.
- Decode errors are textual (category plus offset), not a structured error
  object. Encoding and decoding copy payloads; no performance optimization
  or zero-copy path is claimed in this phase.
