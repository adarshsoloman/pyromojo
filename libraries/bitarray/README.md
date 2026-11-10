# bitarray (Mojo Port)

## Status: NOT STARTED

## Library description

Compact storage and manipulation of bit sequences: bitwise operations, counting,
searching, slicing, packing, and conversion to and from bytes and integers.

## Original Python package

- Package: `bitarray`
- Pinned reference version and license: recorded in
  `python_reference/requirements.txt` when implementation begins, per
  [THIRD_PARTY_NOTICES.md](../../THIRD_PARTY_NOTICES.md).
- Upstream source is not vendored.

## Planned Mojo implementation

A native bit buffer with explicit word size, endianness, and padding rules.
Bit ordering and padding semantics will be documented before implementation,
because they determine compatibility.

## Compatibility objectives

- Match reference bit ordering, padding, and length semantics.
- Match results for logical operations on unequal lengths as the reference
  defines them.
- Match counting, searching, and conversion behaviour for supported methods.
- Document unsupported methods and any intentional deviation.

## Testing requirements

- Mojo unit tests for construction, bitwise operations, counting, and slicing.
- Python compatibility tests against the pinned reference.
- Golden vectors including empty buffers, non-byte-aligned lengths, and all-ones
  and all-zeros patterns.

## Benchmarking requirements

- Small, medium, and large buffers; operations that are compute-bound versus
  memory-bound.
- Three-way comparison: Python reference, native Mojo, Mojo via Python interop.
- Cold compilation and warm execution reported separately.

## Current status

NOT STARTED — placeholder only.
