# bitarray (Mojo Port)

## Status: Phase 0 complete — v0.1 scope frozen, awaiting Phase 1 review

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

## v0.1 scope (frozen)

In scope: mutable bitarrays; packed `UInt8` storage; big/little bit
endianness; construction from bit strings, int iterables, and bytes
(owned-copy import); length/layout introspection; indexing, assignment
(incl. resizing slices), and iteration; cross-endianness comparison and
concatenation; append/extend/insert/delete/pop/remove/clear/reverse/
setall; `+`/`+=`/`*`; `& | ^ ~` with in-place forms (equal endianness
only, unequal lengths rejected); length-preserving shifts; count/find/
index/search (incl. `right=`); `tobytes`/`frombytes`; `to01`/`tolist`;
`fill`/`rotate`/`copy`. Full list with per-item semantics:
[`docs/api-scope.md`](docs/api-scope.md).

Explicitly deferred with recorded reasons: `frozenbitarray` (no
read-only flag, no subclassing emulation), buffer-protocol
interoperability (no shared views), file operations,
`pack`/`unpack` utilities, sorting, `bitarray.util`,
`bitarray.bitfields`, prefix-code machinery, and RLE/sparse helpers.

## Original Python package

- Package: `bitarray` **3.12.3** (import name `bitarray`, Python ≥3.7,
  license **PSF-2.0** — permissive, no copyleft review required).
- Pinned in `python_reference/requirements.txt` when implementation
  begins, per [THIRD_PARTY_NOTICES.md](../../THIRD_PARTY_NOTICES.md).
- Upstream source is not vendored; the C sources were read for
  semantics only.

## Planned Mojo implementation

Native packed-bit buffer (`List[UInt8]` + bit length + endianness
flag), word-at-a-time operations with masked tails, and a framed batch
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

## Testing requirements

- Mojo unit tests for construction, bitwise ops, counting, searching,
  slicing, and boundary lengths (0, 1, 7, 8, 9, 63, 64, 65).
- Python compatibility tests against the pinned reference, including
  randomized differential pairs and cross-endianness cases.
- Golden vectors covering empty buffers, non-byte-aligned lengths,
  all-zeros/all-ones patterns, and word-boundary sizes.

## Benchmarking requirements

- Small, medium, and large buffers; word-parallel ops, search, and
  mutation workloads; equal- and mixed-endianness paths.
- Three-way comparison: naive Python baseline, pinned C reference
  (`bitarray` C extension), native Mojo, in-process.
- Cold compilation and warm execution reported separately.

## Current status

Phase 0 complete and scope frozen: reference pinned and audited,
v0.1 API fixed with deferred items recorded, algorithms mapped to
verified Mojo primitives, benchmark methodology designed. No
production implementation yet — that begins with Phase 1 after
review of this report.
