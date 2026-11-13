# bitarray (Mojo Port)

## Status: v0.1.0 released (`bitarray-v0.1.0`)

Native Mojo packed-bit arrays with parity tests against
`bitarray==3.12.3`: storage and invariants (1A);
construction, indexing, slicing, `to01`/`tolist` (1B);
mutation, concatenation, comparison (1C); bitwise ops and shifts
(1D1); `count`/`search` (1D2); `reverse`/`fill`/`copy`/`rotate`/
`find`/`index` (1D3); byte conversion (`tobytes`/`frombytes`),
canonical framed payloads, batch CLI, and 266 golden vectors (1E).
See [Current status](#current-status) and the
[1E reference probes](docs/phase1e-reference-probes.md).

Phase 0 report: [`PHASE0_RESULTS.md`](PHASE0_RESULTS.md) (§11 records
the frozen decisions, including the initial architecture).
Reference audit: [`docs/reference-audit.md`](docs/reference-audit.md) ·
API scope: [`docs/api-scope.md`](docs/api-scope.md) ·
Algorithm analysis: [`docs/algorithm-analysis.md`](docs/algorithm-analysis.md) ·
Benchmark design: [`docs/benchmark-design.md`](docs/benchmark-design.md).

## Library description

Compact storage and manipulation of bit sequences: bitwise operations,
counting, searching, slicing, packing, and conversion between bytes and
integers, used in compression, cryptography, bioinformatics, and
protocol handling.

## v0.1 scope (frozen) and release contents

The frozen scope is recorded in [`docs/api-scope.md`](docs/api-scope.md).
The v0.1.0 release implements this subset of it: mutable bitarrays;
packed `UInt8` storage; big/little bit endianness; construction from
bit strings, int/bool iterables, and packed bytes (owned-copy import);
length/layout introspection; indexing, assignment (incl. resizing
slices), and iteration; cross-endianness comparison and concatenation;
append/extend/insert/`delete`; `+`/`+=`; `& | ^ ~` with in-place forms
(equal endianness only, unequal lengths rejected); length-preserving
shifts; count/find/index/search (incl. `right=`); `tobytes`/`frombytes`;
`to01`/`tolist`; `fill`/`rotate`/`copy`/`reverse`.

Approved in the frozen scope but not implemented in v0.1.0 (candidates
for a later release, not deferred out): `pop`, `remove`, `clear`,
`setall`, `invert(i)`, `all`/`any`, repetition (`*`/`*=`), and
multi-index deletion (`del a[i:j]`; single-index deletion ships as
`delete(i)`).

Explicitly deferred with recorded reasons: `frozenbitarray` (no
read-only flag, no subclassing emulation), buffer-protocol
interoperability (no shared views), file operations,
`pack`/`unpack` utilities, sorting, `bitarray.util`,
`bitarray.bitfields`, prefix-code machinery, and RLE/sparse helpers.

## Original Python package

- Package: `bitarray` **3.12.3** (import name `bitarray`, Python ≥3.7,
  license **PSF-2.0** — permissive, no copyleft review required).
- Pinned in `python_reference/requirements.txt`
  (`bitarray==3.12.3`), per [THIRD_PARTY_NOTICES.md](../../THIRD_PARTY_NOTICES.md).
- Upstream source is not vendored; the C sources were read for
  semantics only.

## Mojo implementation

Native packed-bit buffer (`List[UInt8]` + bit length + endianness
flag), byte-at-a-time operations with masked tails, and a framed batch
CLI reusing the established transport pattern. The CLI payload carries
packed bytes, the logical bit length, and the endianness explicitly —
length is never inferred from the final byte. Phase 0 validated every
primitive in isolation: packing/extraction, big/little-endian indexing,
UInt64 bitwise ops, guarded shifts, SWAR popcount, allocation/copy/
slice semantics, and packed↔logical round-trips.

## Compatibility objectives

- Match reference bit ordering (within-byte mirroring per endianness),
  padding (`padbits = (8 - n%8) % 8`), and length semantics.
- Match results for logical operations, including unequal-length and
  mixed-endianness rules exactly as the reference defines them.
- Match counting, searching (incl. `right=` variants), and byte
  conversion (`tobytes`/`frombytes`) behaviour. File I/O, buffer
  exports, and `pack`/`unpack` are deferred (see v0.1 scope above).
- Reject what the reference rejects (`ValueError`/`IndexError`/
  `TypeError` parity); document any intentional deviation.

### Known compatibility deviations (verified, intentional)

- Mojo `search()` returns a materialized `List[Int]` of match positions
  instead of Python's lazy `searchiterator`; positions and order are
  identical (empty pattern, bounds, and `right=` included).
- Mojo errors use the general `Error` type with reference message text
  rather than Python's exception hierarchy; tests match on message
  content.
- Mojo's borrow checker rejects direct self-aliasing syntax (`a &= a`,
  `a[1:3] = a`); the same observable behavior is available through an
  explicit snapshot (`a &= a[:]`, `a[1:3] = a[:]`).
- Mojo has no `del a[i]` syntax; single-index deletion is `delete(i)`
  with the reference `__delitem__` semantics and error message.
- Bytes-based construction uses the packed-buffer constructor with an
  explicit logical length (the length is never inferred from bytes);
  `frombytes` appends whole bytes and the caller trims, exactly like
  the reference.

## Testing requirements

- Mojo unit tests for construction, bitwise ops, counting, searching,
  slicing, and boundary lengths (0, 1, 7, 8, 9, 63, 64, 65).
- Python compatibility tests against the pinned reference, including
  randomized differential pairs and cross-endianness cases.
- Golden vectors covering empty buffers, non-byte-aligned lengths,
  all-zeros/all-ones patterns, and word-boundary sizes.
- Framed-protocol tests covering valid and malformed payloads.

## Serialization format

The logical bit length is never inferred from packed bytes. The
canonical payload is:

```text
uint32_be nbits | uint8 endian_id | packed bytes
```

`endian_id` is `0x00` (big) or `0x01` (little); exactly
`ceil(nbits/8)` data bytes follow with zeroed padding bits. The decoder
rejects short/long byte counts, unknown endian ids, and nonzero
padding instead of exposing pad bits as data.

## CLI usage

Build once, then speak the framed batch protocol on stdin/stdout
(`uint32_be length | uint8 opcode | payload` per request;
`uint32_be length | uint8 status | payload` per response):

```bash
.venv/bin/mojo build libraries/bitarray/mojo/cli.mojo \
    -I libraries/bitarray/mojo -o build/bitarray_cli
```

Opcodes: `0x01` ping, `0x02` echo, `0x10` decode (canonical payload →
ASCII `0`/`1` string), `0x11` encode (endian id + ASCII bits →
canonical payload). Status `0` is success, `1` is an error frame whose
payload is the message. A clean EOF ends the session with exit code 0;
framing errors reply once and exit non-zero, matching the other CLIs.

## Golden vectors

266 deterministic cases in `tests/vectors/bitarray_vectors.json`
(lengths 0–65, zeros/ones/alternating/single-bit/sparse/dense/random
patterns, both endiannesses), each with logical bits, packed bytes, and
the canonical framed payload, all generated from `bitarray==3.12.3`:

```bash
.venv/bin/python libraries/bitarray/python_reference/generate_vectors.py --check
```

Regenerate intentionally (without `--check`) only when reference
behavior changes; the repo runner fails on drift. The same generator
emits the typed Mojo case module consumed by the native golden tests.

## Benchmarking requirements

- Small, medium, and large buffers; word-parallel ops, search, and
  mutation workloads; equal- and mixed-endianness paths.
- Three-way comparison: naive Python baseline, pinned C reference
  (`bitarray` C extension), native Mojo, in-process.
- Cold compilation and warm execution reported separately.

## Current status

v0.1.0 released (`bitarray-v0.1.0`): the release API above is
implemented in native Mojo with parity tests against
`bitarray==3.12.3` — 74 native Mojo tests, 391 Python compatibility
tests, and 266 golden vectors with drift checking, plus the framed
batch CLI. See the repository release notes for the full verification
summary.
