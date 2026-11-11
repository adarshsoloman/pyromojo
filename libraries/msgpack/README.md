# Msgpack (Mojo Port)

## Status: PHASE 6 INTEGRATION COMPLETE

The full v0.1 type set — integers, Float32/Float64, strings, binary values,
nil and bool (top level and nested), recursively nested arrays and maps, all
eight extension families, and the standard timestamp extension — encodes and
decodes with exact-byte and cross-language tests. The batch CLI is audited
end to end and the repository runners (`scripts/run_all_tests.py`,
`scripts/check_compatibility.py`) execute the whole suite reproducibly.
See [PHASE6_RESULTS.md](PHASE6_RESULTS.md).

## Library description

MessagePack is a compact binary serialization format. It encodes integers,
floats, strings, binary blobs, arrays, maps, extension values, and timestamps
into a self-describing byte stream that is smaller than JSON and cheaper to
parse, while remaining cross-language.

## Original Python package

- Package: `msgpack` (msgpack-python)
- Reference role: produces authoritative encoded bytes and decodes reference
  inputs for compatibility comparison.
- Pin policy: `msgpack==1.2.4`, recorded in
  `python_reference/requirements.txt` and the project dev dependencies, per
  [THIRD_PARTY_NOTICES.md](../../THIRD_PARTY_NOTICES.md).
- Upstream source is not vendored.

## Planned Mojo implementation

A native encoder and decoder operating on byte buffers, exposed through a
length-prefixed batch CLI so Python can compare results. The native path must
not delegate encoding or decoding work to the Python package.

Layout:

- `mojo/` — `Value`, integer/scalar codecs, framing protocol, and the batch CLI
- `python_reference/` — vector generator, reference driver, depth probe, pins
- `tests/` — Mojo unit tests, Python compatibility tests, golden vectors
- `benchmarks/` — cold-compile and warm-execution benchmarks
- `examples/` — minimal encode/decode usage
- `docs/batch_protocol.md` — CLI wire protocol

## Compatibility objectives

- Produce byte-identical output to the reference for the supported v0.1 type
  set, or document any intentional difference.
- Decode reference-produced streams to equivalent values.
- Match reference error behaviour for malformed input: fail, do not silently
  accept.
- Preserve integer width and signedness where the format distinguishes them.
  MessagePack has no independent signedness bit for non-negative wire values:
  positive fixint and uint8/16/32/64 decode with an unsigned tag even when the
  encoder started from a signed value.
- Preserve map ordering and duplicate keys as ordered pairs.
- Handle nesting without unbounded recursion or silent truncation; the default
  depth limit is 128, below the reference C extension's 1024.
- Cover extension types and timestamps, including negative timestamp seconds.

## v0.1 scope

The initial version targets the following, in this order:

1. **Integer encoding** — positive fixint, negative fixint, and the fixed-width
   integer families, selecting the shortest valid representation.
2. **Floating-point encoding** — 32-bit and 64-bit floats, including
   round-trip preservation of the reference's choice of width.
3. **String encoding** — fixstr, str8, str16, str32, including UTF-8 byte
   length handling.
4. **Binary encoding** — bin8, bin16, bin32.
5. **Arrays** — fixarray and array16/array32, arbitrarily nested.
6. **Maps** — fixmap and map16/map32, including nested maps and mixed value
   types already in scope.
7. **Decoding** — the full v0.1 type set, with exact consumption of input and
   rejection of trailing or truncated data as the reference does.
8. **Nested structures** — combinations of arrays and maps to a tested depth.
9. **Extension types** — fixext1/2/4/8/16 and ext8/16/32.
10. **Timestamps** — timestamp32, timestamp64, and timestamp96, including
    negative seconds.
11. **Invalid-input handling** — truncated headers, invalid type bytes,
    out-of-range lengths, reserved markers, and malformed UTF-8 where the
    reference rejects it.

Out of scope for v0.1: streaming unpackers, canonical/deterministic mode, and
Python-specific object hooks. These may be added after v0.1 is verified.

## Testing requirements

- Mojo unit tests for each type family, boundary values, and invalid inputs.
- Python compatibility tests comparing encoded bytes and decoded values against
  the pinned reference.
- Golden vectors committed under `tests/vectors/`, validated against the shared
  schema, covering every item in the v0.1 scope.
- Invalid-input vectors that assert failure rather than corruption.
- `python_reference/generate_vectors.py --check` must pass; hand-edited vectors
  are rejected by the drift test.

Install test dependencies and run the suite:

```bash
uv sync --extra dev
.venv/bin/pytest -q
```

## Benchmarking requirements

- Encode and decode benchmarks for small, medium, and large payloads.
- Three-way comparison: Python reference, native Mojo, Mojo via Python interop.
- Cold compilation and warm execution reported separately.
- Environment metadata and configuration recorded per
  [docs/benchmarks/README.md](../../docs/benchmarks/README.md).

## Current status

Phase 6 scope complete: 162 golden cases covering integers, Float32 and
Float64 bit patterns, UTF-8 strings, arbitrary binary payloads, recursively
nested arrays and maps, all extension markers (including empty payloads and
length boundaries), and all three timestamp representations (including
negative seconds and nanosecond boundaries), with native exact-byte tests,
bidirectional CLI compatibility, and repository-level runners. Top-level
nil and bool are supported; the remaining deviations (negative extension
codes, 128 vs 1024 depth limit, textual errors) are documented and pinned by
tests.
