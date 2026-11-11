# MessagePack Phase 4 results: recursive arrays and maps

Phase 4 adds native Mojo encoding and decoding for recursively nested arrays
and maps with depth and resource limits, a recursive CLI transfer model,
golden vectors covering container boundaries and malformed containers, and
cross-language compatibility tests against both the C and fallback Python
reference decoders. Extensions and timestamps remain unimplemented, and bare
top-level nil and bool keep their Phase 1 `UNIMPLEMENTED` response.

## Files

Created:

- `libraries/msgpack/mojo/mojo_msgpack/container.mojo` — recursive array/map
  wire codecs, recursive CLI transfer models, depth and item-count limits.
- `libraries/msgpack/tests/mojo/test_container_codec.mojo` — 13 native tests
  for exact bytes, marker boundaries, nesting depth, resource limits,
  malformed containers, and model roundtrips.
- `libraries/msgpack/tests/python_compat/test_container_compat.py` — 19
  pytest cases for bidirectional cross-language compatibility (C and fallback
  decoders), depth/limit boundaries, and error behaviour.
- `libraries/msgpack/PHASE4_RESULTS.md` — this report.

Modified:

- `mojo/cli.mojo` — recursive `DECODE`/`ENCODE` via the container codec; bare
  top-level nil/bool still return `UNIMPLEMENTED`.
- `mojo/mojo_msgpack/value.mojo` — added `DEFAULT_MAX_CONTAINER_ITEMS`
  (1,000,000) next to `DEFAULT_MAX_DEPTH` (128).
- `python_reference/generate_vectors.py` — schema/generator 1.3.0, container
  boundary and nested cases, container error cases.
- `tests/mojo/generated_vectors.mojo` — regenerated 141-case module.
- `tests/mojo/test_generated_vectors.mojo` — decodes and re-encodes all 17
  supported array/map golden cases.
- `tests/vectors/msgpack_vectors.json` — expanded to 141 cases.
- `shared/test_vectors/schema/msgpack_vectors.schema.json` — schema 1.3.0.
- `shared/validation/msgpack_vectors.py` — schema/generator 1.3.0.
- `libraries/msgpack/docs/batch_protocol.md` — recursive array/map models,
  limits, and map limitations.
- `libraries/msgpack/README.md`, `README.md`, `docs/roadmap.md` — status and
  compatibility notes.

## Implemented format families

| Category | Markers |
|----------|---------|
| Array | fixarray (`90`-`9f`), array16 (`dc`), array32 (`dd`) |
| Map | fixmap (`80`-`8f`), map16 (`de`), map32 (`df`) |
| Nil/bool children | `c0`, `c2`, `c3` (nested only) |

Wire encoding selects the shortest representation from the payload count and
recurses into children. Decoding enforces depth (`max_depth`, default 128)
and item counts (`max_container_items`, default 1,000,000) before allocation:
a non-empty container is rejected with `depth-exceeded` when the remaining
depth is 1, a declared count above the limit fails with `container-limit`, and
a declared count larger than the remaining bytes fails with `truncated`. A
scalar has depth 1; a container has depth 1 plus its deepest child, so 127
nested arrays around a scalar is the deepest value at the default limit.

The recursive CLI model frames every child model with its length:

```
array := 0x14 | uint32_be count | (uint32_be length | model) * count
map   := 0x15 | uint32_be pairs | key/value frames * pairs
nil/false/true := 0xc0 / 0xc2 / 0xc3
```

Scalar models are unchanged. A lone `0x20` model still reports
`invalid-model`, and bare top-level `0xc0`/`0xc2`/`0xc3` still report
`UNIMPLEMENTED`, preserving the Phase 1 transfer behavior.

## Boundary test coverage

Arrays:

- Empty, fixarray max (15), array16 min (16), array16 max (65,535), array32
  min (65,536, repeated-nil compact model).
- Mixed scalars with nil/bool children, nested arrays, and a nested
  array/map/bool/empty-array case.
- Truncated fixarray/array16/array32 headers and missing children; a reserved
  `c1` child; trailing data after a complete array.
- A declared array32 count of 4,294,967,295 (reference: `ValueError: exceeds
  max_array_len`; native: `container-limit` before allocation).

Maps:

- Empty, fixmap max (15 pairs), map16 min (16), map16 max (65,535, duplicate
  key/value decode-only), map32 min (65,536 repeated pairs, decode-only).
- Mixed-type keys (string, int, bool), array keys, duplicate keys preserved as
  ordered pairs, nested containers as keys and values.
- Truncated map16/map32 headers and a truncated map value; a declared map32
  count of 4,294,967,295 (reference: `ValueError: exceeds max_map_len`;
  native: `container-limit` before allocation).

Depth:

- 127 nested arrays decode and re-encode (depth 128); 128 nested arrays fail
  with `depth-exceeded`. An empty container is accepted at `max_depth` 1;
  any non-empty container at depth 1 is rejected.
- The existing reference depth vector (1025 nested arrays) still asserts the
  reference `StackError`; the native CLI reports `depth-exceeded` for the
  same input, documenting the intentional limit difference (128 vs 1024).

The bundle now contains 141 cases: 35 integer, 26 float, 12 string, 7 binary,
8 array, 9 map, 8 extension, 6 timestamp, 2 bool, 1 nil, and 27 error cases.

## Cross-language compatibility

For all 12 array/map roundtrip golden cases:

1. The Python C packing of the model matches the golden bytes.
2. Mojo `DECODE` returns the recursive model matching the tagged value.
3. Mojo `ENCODE` of the `model_for` bytes matches the golden bytes.
4. Both the C and `msgpack.fallback` decoders accept the golden and
   re-encoded bytes with equal results.

For all 5 map decode-only cases (duplicate keys, array keys, repeated
map16/map32 pairs, nested mixed maps), Mojo `DECODE` preserves pair order and
`ENCODE` reproduces the golden bytes exactly; duplicate keys are asserted as
ordered pairs. The fallback `Packer` output also decodes natively.

Map limitations are documented: Python `dict` cannot represent duplicate keys
or unhashable keys (arrays), so reference code uses `object_pairs_hook` with
`strict_map_key=False`; the native model preserves both. Float32 behavior,
signed-positive integer decoding, and all Phase 1-3 stubs are unchanged.

## Test results

```text
$ .venv/bin/pytest -q
91 passed in 9.61s

$ ./build/test_depth
Summary [ 0.045 ] 8 tests run: 8 passed , 0 failed , 0 skipped

$ ./build/test_integer_codec
Summary [ 0.060 ] 12 tests run: 12 passed , 0 failed , 0 skipped

$ ./build/test_generated_vectors
Summary [ 49.226 ] 11 tests run: 11 passed , 0 failed , 0 skipped

$ ./build/test_scalar_codec
Summary [ 0.601 ] 13 tests run: 13 passed , 0 failed , 0 skipped

$ ./build/test_container_codec
Summary [ 12.073 ] 13 tests run: 13 passed , 0 failed , 0 skipped

$ .venv/bin/ruff check libraries shared scripts
All checks passed!

$ .venv/bin/ruff format --check libraries shared scripts
22 files already formatted

$ .venv/bin/python libraries/msgpack/python_reference/generate_vectors.py --check
vectors: 141 cases, committed artifacts are current
```

The bundle and schema also validate under the stdlib validator
(`test_bundle_is_structurally_valid`); the JSON Schema Draft 2020-12
one-off check needs the optional `jsonschema` package, which is not
installed in this environment.

## Remaining limitations

- Extensions and timestamps still return `UNIMPLEMENTED` from the CLI
  (verified for ext8 and timestamp32 children inside arrays).
- Bare top-level nil and bool models keep the Phase 1 `UNIMPLEMENTED`
  response; nested nil/bool are fully supported.
- The native default depth limit is 128; the reference accepts up to 1024.
- The reference caps declared container counts against the input buffer size
  (`exceeds max_array_len` / `exceeds max_map_len`); the native side reports
  `container-limit` against the 1,000,000-item cap. Both reject.
- Python's default mapping type collapses duplicate keys and forbids
  unhashable keys; ordered/duplicate semantics exist only through
  `object_pairs_hook` and the native model.
- Decode errors are textual (category plus offset), not a structured error
  object. Encoding and decoding copy payloads; no performance optimization
  or zero-copy path is claimed in this phase.
