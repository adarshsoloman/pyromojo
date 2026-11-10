# Msgpack (Mojo Port)

## Status: NOT STARTED

No implementation exists yet. This README defines the intended scope of the
first port.

## Library description

MessagePack is a compact binary serialization format. It encodes integers,
floats, strings, binary blobs, arrays, and maps into a self-describing byte
stream that is smaller than JSON and cheaper to parse, while remaining
cross-language.

## Original Python package

- Package: `msgpack` (msgpack-python)
- Reference role: produces authoritative encoded bytes and decodes reference
  inputs for compatibility comparison.
- Pin policy: the exact reference version is recorded in
  `python_reference/requirements.txt` when implementation begins, per
  [THIRD_PARTY_NOTICES.md](../../THIRD_PARTY_NOTICES.md).
- Upstream source is not vendored.

## Planned Mojo implementation

A native encoder and decoder operating on byte buffers, exposed through a thin,
tested boundary that lets Python compare results. The native path must not
delegate encoding or decoding work to the Python package.

Layout:

- `mojo/` — native sources (empty, pending Phase 2)
- `python_reference/` — reference driver and pinned requirements
- `tests/` — Mojo unit tests, Python compatibility tests, golden vectors
- `benchmarks/` — cold-compile and warm-execution benchmarks
- `examples/` — minimal encode/decode usage

## Compatibility objectives

- Produce byte-identical output to the reference for the supported v0.1 type
  set, or document any intentional difference.
- Decode reference-produced streams to equivalent values.
- Match reference error behaviour for malformed input: fail, do not silently
  accept.
- Preserve integer width and signedness where the format distinguishes them.
- Preserve map ordering as the reference does for the supported types.
- Handle nesting without unbounded recursion or silent truncation.

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
9. **Invalid-input handling** — truncated headers, invalid type bytes,
   out-of-range lengths, and malformed UTF-8 where the reference rejects it.

Out of scope for v0.1: extension types, timestamps, streaming unpackers,
canonical/deterministic mode, and Python-specific object hooks. These may be
added after v0.1 is verified.

## Testing requirements

- Mojo unit tests for each type family, boundary values, and invalid inputs.
- Python compatibility tests comparing encoded bytes and decoded values against
  the pinned reference.
- Golden vectors committed under `tests/vectors/`, validated against the shared
  schema, covering every item in the v0.1 scope.
- Invalid-input vectors that assert failure rather than corruption.

## Benchmarking requirements

- Encode and decode benchmarks for small, medium, and large payloads.
- Three-way comparison: Python reference, native Mojo, Mojo via Python interop.
- Cold compilation and warm execution reported separately.
- Environment metadata and configuration recorded per
  [docs/benchmarks/README.md](../../docs/benchmarks/README.md).

## Current status

NOT STARTED — directory scaffold only.
