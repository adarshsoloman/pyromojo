# Bitarray — Phase 0 results

Status: investigation complete, no production code written. All claims
below are either directly observed (with the probe file named) or marked
**recommendation**. Nothing here claims an unrun experiment passed.

Probes: `experiments/probe_reference.py` →
`experiments/reference_probe_output.txt` (216 lines);
`experiments/probe_edge_cases.py` →
`experiments/edge_cases_output.txt` (105 lines);
`experiments/toolchain_validation/bitarray/packing.mojo`,
`words.mojo`, `storage.mojo` (with matching `*_output.txt`).
Docs: `docs/reference-audit.md`, `docs/api-scope.md`,
`docs/algorithm-analysis.md`, `docs/benchmark-design.md`.

## 1. Reference audit

Pinned: `bitarray==3.12.3` (import name `bitarray`, Python ≥3.7,
`License-Expression: PSF-2.0`, zero dependencies), installed
ephemerally into `.venv` via `uv pip install` for black-box
observation only. `pyproject.toml` and dependency files are untouched
in Phase 0 (the formal pin belongs in
`python_reference/requirements.txt`, created when implementation
begins — same convention as the Levenshtein port).

`bitarray` is a pure-C extension (`bitarray/_bitarray.c`,
`bitarray/_util.c`) plus a thin Python layer (`util.py`,
`bitfields.py`) and type stubs. The C header (`bitarray.h`) gives the
complete storage model: `ob_item` byte buffer, `allocated` bytes,
`nbits` bits, endianness flag, `BYTES(bits) = (bits + 7) >> 3`,
`PADBITS = (8 - nbits % 8) % 8`, and per-bit access as
`buf[i >> 8]` with mask `1 << (i % 8)` (little-endian) or
`1 << (7 - (i % 8))` (big-endian).

**License decision (recorded): PSF-2.0 is permissive — no copyleft
review is required.** No code is vendored; the C sources were read for
semantics only, per `THIRD_PARTY_NOTICES.md`.

## 2. API scope (v0.1, frozen)

Frozen per Phase 0 finalization; full rationale and trade-offs in
`docs/api-scope.md`. In scope: mutable `BitArray` only; packed
`UInt8` storage; big/little bit endianness; construction from
bit-strings, int iterables, and bytes (owned-copy import);
length/layout introspection; indexing/assignment (incl. resizing
slices) and iteration; cross-endianness comparison and concatenation;
append/extend/insert/delete/pop/remove/clear/reverse/setall;
`+`/`+=`/`*`; `& | ^ ~` with in-place forms (equal endianness only,
unequal lengths rejected); length-preserving shifts; count/find/
index/search (incl. `right=`); `tobytes`/`frombytes`;
`to01`/`tolist`; `fill`/`rotate`/`copy`.

Deferred with recorded reasons: `frozenbitarray` (in full — no
read-only flag, no subclassing emulation); buffer-protocol
interoperability (owned copies only, no shared views); file
operations; `pack`/`unpack`; sorting; `bitarray.util`;
`bitarray.bitfields`; prefix-code machinery; RLE/sparse helpers;
pickling; threading guarantees; anything absent from the reference.

## 3. Interop surface

No Python extension and no MessagePack changes in Phase 0. The v0.1
interop surface will be a **framed Mojo CLI reusing the established
framing pattern** (`uint32_be length | uint8 opcode | payload`,
response `uint8 status | payload`), with new opcodes for bitarray
operations. Rationale: it reuses proven transport and validation code
and keeps Python↔Mojo comparisons in-process-exact on both sides of
the frame. Golden vectors plus randomized differential comparison
(seed fixed) run through the CLI. A native Python binding is
explicitly out of scope until the algorithm surface is pinned.

Frozen wire-format decision (Phase 0 finalization): the payload
explicitly carries packed byte data, the logical bit length
(`nbits`), and the bit endianness (`endian`). The logical length is
never inferred from the final byte — receivers must use the carried
length and ignore (on read) or zero (on write) pad bits beyond it.
This matches the existing msgpack/levenshtein convention of
explicit-length framing with no silent coercion.

## 4. Performance strategy

The three-way model from the brief is confirmed feasible but
redefined by what the components are: (1) **naive pure-Python
bit operations** over ints/lists (honest floor), (2) **pinned
`bitarray` C extension** (both compatibility oracle and ceiling —
there is no separate pure-Python fallback worth benchmarking),
(3) **native Mojo**. Feasibility timings on this machine: bitwise AND
over 1M bits ≈ 5 µs, `count()` ≈ 24 µs content-independent, `tobytes`
≈ 2.4 µs, LCS-style `search` ≈ 6.7 ms at 1M (the expensive path).
Sub-microsecond medians at small sizes require min-of-N reporting
with warmup; a one-off 2 ms `count` outlier traced to cold pages
confirms warmup must touch real buffers, not just repeat calls.

## 5. Unicode handling

Not applicable as text semantics: bitarray operates on bits, with no
normalization, encoding, or grapheme concepts. The fixed mapping is:
Python `str` inputs are restricted to `'0'`/`'1'` characters (others
raise `ValueError`); `bytes` inputs map whole bytes (one byte → one
bit, `0x00`→0 else 1) and are never UTF-8-decoded; non-UTF-8 byte
payloads are therefore ordinary data, not errors. Combining
characters, astral code points, and ZWJ sequences never appear as
such — only their UTF-8 bytes would, if a caller encodes them first.

## 6. Correctness strategy

Golden values come from captured probe outputs, never from memory;
a `generate_vectors.py` with a `--check` drift gate (msgpack/
levenshtein pattern) lands in Phase 1. Compatibility layers:
(1) `test_reference_assumptions.py` pinning oracle edge behavior
(zero-length bitwise ops, shift length preservation, error types and
messages, in-scope `fill`/`rotate` semantics); (2) golden vectors
covering empty,
1/7/8/9-bit, 63/64/65-bit, and multiword sizes in both endiannesses;
(3) randomized differential tests against the pinned C implementation
(including weighted-free but affix-heavy pairs, both argument orders,
and mixed-endianness comparison paths); (4) error-path parity
(`IndexError` bounds, `ValueError` mismatches, `TypeError` operand
and read-only violations). No silent coercion anywhere: every probed
invalid input raises.

## 7. Mojo 1.2.0 capabilities (verified)

`List[UInt8]` allocation/indexing/assignment, `len()`, `min`/`max`,
and explicit-width integer ops all work (`packing.mojo`,
`storage.mojo`, `words.mojo` — all green). Two hazards confirmed with
dedicated probes, both matching Phase 0 findings from the
Levenshtein port:

- **Full-width shifts are target-defined**: constant `<< 64` is a
  compile error; runtime `1 << 64` folds to `1` (x86 count masking).
  All shift amounts must be guarded to `< 64`, with explicit branches
  for the width case (validated: `shl_guarded`/`shr_guarded`,
  `mask_low_bits` covering 0..64+).
- **Integer arithmetic wraps silently**: `MAX + 1 == 0`, `0 - 1 ==
  MAX`. Multiword carry/borrow must be explicit (`total < x`
  overflow test; `sub > u` borrow test) — validated in the bit-vector
  probes.
- **No builtin popcount**: `std.bit` has no `popcount`,
  `UInt64` has no `count_ones`. SWAR and nibble-table
  implementations agree on adversarial inputs; SWAR recommended,
  table retained as oracle.
- **Mojo strings are UTF-8 views**: no `len(str)`, no `s[i]` —
  explicit `byte_length()` / `s[byte=i]` required even in test
  helpers. Hex literals are `Int`, not `UInt8` (explicit casts).
- `Dict[Int, List[UInt8]]` Peq tables work as in the Myers probes and
  remain the recommended structure for bitmasks.

## 8. Benchmark design

Forty-one-analogous workloads (see `docs/benchmark-design.md`):
sizes 0/1/7/8/9, 63/64/65, 1 KiB/64 KiB/1 MiB/8 MiB-sparse;
all-zero/all-one/alternating/random-dense/random-sparse/single-bit;
both endiannesses; equal/unequal lengths. Operations: indexing,
mutation, AND/OR/XOR/NOT, popcount, search, append/extend, shifts,
fill, rotate, `tobytes`/`frombytes` round-trips (deferred ops —
`tofile`/`fromfile`, `bytereverse`, `pack`/`unpack`, `sort` — are
not benchmarked in v0.1). Timing
separates algorithm, allocation, conversion, serialization, and
cold-compile/RSS; correctness gates fail the run (exact value
equality, error-message parity, length/pad invariants, min>0,
scaling spot-checks, repeat-run agreement).

## 9. Project conventions (applicable, unchanged)

Framed CLI protocol, deterministic generators with drift gates, typed
golden vectors, in-process `bench.mojo`, `test_reference_assumptions.py`
pattern, ruff line-length 100 (`E,F,I,UP,B,SIM`, double quotes),
pytest under `libraries/` (probe scripts are named `probe_*`, never
`test_*`, so the suite stays green), `.venv` Mojo 1.2.0 only.
`run_all_tests.py` / `check_compatibility.py` already cover
msgpack+levenshtein; bitarray integration (drift check, Mojo test
list, compat entry) is a Phase 1 task, flagged here — not done now.

## 10. Risk register

1. **Shift-width UB** — mitigated by the guard discipline in §7,
   to be encoded as regression tests in Phase 1.
2. **Silent wraparound** — mitigated by explicit carry/borrow in all
   multiword code; single-word ops cannot overflow by construction
   (accumulators sized ≥ result).
3. **Scope creep into util/bitfields/Huffman** — mitigated by §2's
   explicit exclusion list with reasons.
4. **Endianness confusion** — mitigated by the audit's byte-map table
   and per-endianness golden vectors (bit order, not byte order).
5. **`pack`/`unpack` misreading** — recorded as byte↔bit maps, not
   bit-packing; test names must say so.
6. **Performance-claim overreach on search** — `search` is the only
   superlinear path; v0.1 ships the straightforward scan, with
   word-skipping as documented future work.

## 11. Phase 1 readiness and next actions

Ready to proceed, with these inputs: (1) the frozen scope in §2
(reviewed, not re-opened without a new decision record);
(2) create `python_reference/requirements.txt` with
`bitarray==3.12.3` and register the dev dependency per project
convention; (3) implement the initial design below with the §7 guards
as acceptance tests; (4) build golden vectors + drift gate before any
optimization; (5) wire `run_all_tests.py` / `check_compatibility.py`
when the first tests land.

### Resolved decisions (previously open questions)

1. **`frozenbitarray` is deferred in full.** No distinct Mojo type,
   no read-only flag, no subclassing emulation in v0.1.
2. **Wire format is explicit** (see §3): packed bytes + `nbits` +
   `endian`; pad bits documented as ignored-on-read, zeroed-on-write.
3. **`sort` is deferred.** Trivial given `count`, and no v0.1
   workload or benchmark needs it.

### Initial architecture (implementation candidate)

```text
BitArray
├── buffer: List[UInt8]
├── length: Int
└── endian: Endian
```

Invariants (all enforced, all tested in Phase 1):
- Padding bits remain zero (writes mask them; reads ignore them).
- Logical length is independent of physical byte length
  (`len(buffer) == ceil(length / 8)` at rest).
- Indexing follows the selected bit endianness
  (`1 << (i % 8)` little-endian, `1 << (7 - (i % 8))` big-endian).
- Mutations preserve storage invariants (no silent growth beyond
  amortized append/extend; no aliasing of caller buffers).
- Invalid operations produce explicit errors (the §2 error contract),
  never silent truncation or coercion.

This is an initial design, not permission for unvalidated low-level
memory optimizations: word-at-a-time access, buffer reuse, and SIMD
all wait for benchmark justification in their own phase.

## 12. Experiment inventory

- `experiments/probe_reference.py` →
  `experiments/reference_probe_output.txt` (216 lines, exit 0)
- `experiments/probe_edge_cases.py` →
  `experiments/edge_cases_output.txt` (105 lines, exit 0)
- `experiments/toolchain_validation/bitarray/packing.mojo` →
  `packing_output.txt` (all asserts pass)
- `experiments/toolchain_validation/bitarray/words.mojo` →
  `words_output.txt` (all asserts pass)
- `experiments/toolchain_validation/bitarray/storage.mojo` →
  `storage_output.txt` (all asserts pass)
- `/tmp/mojo_cap_check.mojo`, `/tmp/mojo_pop*.mojo`,
  `/tmp/mojo_bit.mojo`, `/tmp/lcs_probe*.mojo` — scratch only,
  **not** in the repo.
