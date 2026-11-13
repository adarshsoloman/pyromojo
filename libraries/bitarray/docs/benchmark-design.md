# Benchmark design: bitarray v0.1 (proposal, not executed)

Phase 0 does not run final benchmarks. This document fixes the
methodology so Phase 1+ can execute it unchanged, following the
established project conventions (deterministic workloads, in-process
native timing, cold-compile reported separately, raw datasets
git-ignored, curated release notes committed).

## Paths to compare

1. **Naive baseline** — pure-Python bit operations over Python ints
   or lists (honest floor, not the reference).
2. **Reference** — pinned `bitarray==3.14.6` C implementation (ceiling
   for most ops; the oracle for correctness, not a competitor to beat
   on principle).
3. **Native Mojo** — in-process timing of the ported operations via a
   `bench`-style harness, same framing discipline as the Levenshtein
   benchmarks (inputs ferried once, outside timed regions).

`Mojo time / comparison time` on medians throughout; below 1.0 means
Mojo is faster. Report per-operation tables, never a single blended
speedup.

## Workload categories (deterministic, seeded RNG)

- **Sizes**: 0, 1, 7, 8, 9 bits (sub-byte and boundary);
  63/64/65 bits (sub-word, word, word+1); 1 KiB, 64 KiB, 1 MiB bits;
  a sparse large case (e.g. 8 MiB mostly zeros) for count/search.
- **Contents**: all-zero, all-one, alternating `10…`, random dense,
  random sparse (p=0.01), single-bit-set, ZWJ-free ASCII-derived bytes
  for realistic mixes.
- **Endianness**: every content case in both big- and little-endian;
  cross-endianness pairs for comparison/concat paths only (bitwise
  paths must error — benchmark the error path once for overhead, not
  for speed).
- **Lengths**: equal-length pairs for bitwise ops; unequal lengths
  for comparison/concat/extend paths; non-multiple-of-8 and
  non-multiple-of-64 lengths explicitly included.

## Operations to measure

Indexing, item assignment, slicing, append, extend (incl. self-extend),
insert, delete, pop, reverse, setall, count (with and without pattern),
find/index/search (hit at start/middle/end, miss), AND/OR/XOR/NOT
(in-place and copying), shifts by 0/1/7/8/63/64/65/large, tobytes/
frombytes round-trips, rotate, fill.

Deferred ops (`tofile`/`fromfile`, `bytereverse`, `pack`/`unpack`,
`sort`, `frozenbitarray`, `util`/`bitfields` functions) are
*not* benchmarked in v0.1 — no harness code paths for them, so a
later phase cannot silently inherit unmeasured coverage.

## What each measurement must isolate

- **Algorithm time**: timed region contains only the operation on
  pre-built inputs (no allocation of inputs, no reference calls).
- **Allocation**: report growth workloads separately (append/extend
  from empty to N); do not mix allocator cost into per-op latencies.
- **Conversion**: `to_codepoints`-style materialization does not exist
  here, but bytes↔bits conversion (`tobytes`/`frombytes`) is timed as
  its own workload, never hidden inside other ops.
- **Serialization**: file I/O timed separately from in-memory ops;
  state tmpfs vs real disk explicitly.
- **Startup/compilation**: cold `mojo build` time and binary size
  reported once per suite, never mixed into medians.
- **Python interop**: out of scope (same project policy as msgpack);
  state the gap instead of measuring around it.

## Correctness gates (fail the run)

- Exact value equality vs the pinned reference on every workload
  (bit-exact `to01`/`tobytes` comparison, not statistical).
- Error parity: every error case must raise the same exception type
  with equivalent semantics (exact message text where the reference
  is stable, e.g. `ValueError: bitarrays of equal bit-endianness
  expected`).
- Length/pad invariants after every op: `nbytes == ceil(len/8)`,
  `padbits == (8 - len % 8) % 8`.
- Timer gates: warmup excluded, ≥25 samples, every median and sample
  strictly positive; scalingspot-checks (larger inputs must not be
  faster on linear ops).
- Repeat-run directional agreement before publishing any comparison.

## Memory observations

- Record peak RSS for the largest workload (isolated child process),
  allocator state excluded from claims as in prior phases.
- Track bytes-per-bit overhead at small sizes (header + rounding) vs
  asymptotic 1/8 byte-per-bit; report the crossover where the port
  undercuts the reference's per-object cost, if any.
- No generated reports or scratch data committed; only the curated
  release summary lands in `docs/benchmarks/releases/`.
