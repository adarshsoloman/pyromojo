# API scope: bitarray v0.1 (frozen)

Frozen per Phase 0 finalization. Every entry below was observed against
`bitarray==3.12.3` (see `docs/reference-audit.md` and
`experiments/`). Nothing here is implemented yet.

## Category A — core v0.1 (frozen in scope)

Rationale: without these there is no usable bit container, and each
has exact, probed reference semantics (no behavioral latitude).

- **Construction**: `bitarray([initializer][, endian])` from bit
  strings (`'101'`, whitespace/underscores allowed), int iterables,
  and `bytes` (imported as raw packed bits into **owned, mutable**
  storage). Rejects bad characters (`ValueError`), non-iterables
  (`TypeError`), bad `endian` (`ValueError`).
- **Packed `UInt8` storage with length and layout introspection**:
  contiguous byte buffer holding `ceil(n/8)` bytes; `len()`,
  `nbytes`, `padbits` ((8 - n%8) % 8), `.endian` string.
  Complexity O(1).
- **Indexing/assignment**: `a[i]` (incl. negatives; `IndexError`
  outside), `a[i] = 0/1` (`ValueError` otherwise), slicing with
  steps and reversal, **resizing slice assignment** (mismatched
  lengths legal, like `list`).
- **Iteration/comparison/concatenation**: yields Python `int`s;
  `==`/`!=` compare logical bits across endianness; full ordering is
  lexicographic with shorter-prefix-first; `in` accepts int or
  bitarray; `+`/`+=` concatenate (mixed-endianness operands allowed,
  compare by logical bits).
  (`bitarray` itself is unhashable — hashing belongs with the
  deferred immutable variant.)
- **Mutation**: `append`, `extend` (str/list/bitarray), `insert`
  (negative allowed, past-end appends), `pop` (incl. negative index),
  `remove` (first match; missing raises), `clear` (length 0, buffer
  retained), `reverse`, `setall`, `del a[i]` / `del a[i:j]`,
  `+`/`+=`/`*`/`*=` (negative repeat → empty).
- **Bitwise core**: `& | ^ ~` plus in-place variants and `invert()`;
  **equal endianness required** (`ValueError` otherwise);
  **unequal lengths rejected** (no implicit padding); shifts preserve
  length (bits fall off, zeros fill in); negative shifts rejected.
- **Counting/searching**: `count(v[, start[, stop[, step]]])`,
  `find` (missing → -1), `index` (missing → `ValueError`), `search`
  (all offsets, `right=1` for right-to-left), `all`/`any`.
- **Byte conversion**: `tobytes`/`frombytes` (whole bytes; caller
  trims to length). No file objects, no buffer exports — see below.
- **Small transforms**: `fill()` (zero-pad to a byte boundary,
  returns pad count), `rotate(k)` (right rotation by `k mod n`),
  `copy()` (independent; no aliasing observable).
- **Error contract**: `IndexError` for bounds/empty-pop;
  `ValueError` for bad values, unequal-length bitwise ops,
  cross-endianness bitwise ops, missing items; `TypeError` for wrong
  operand types. No silent truncation or coercion anywhere.

## Category B — deferred to future releases

Each item is separable with its own edge cases; all are explicitly
**out of v0.1**:

- **`frozenbitarray`** (deferred in full — see "Resolved decisions"
  below). Includes its hashability and its concat typing rules
  (frozen+frozen→frozen, frozen+plain→frozen, plain+frozen→plain).
- **Buffer-protocol interoperability**: exporting buffers
  (`memoryview(a)`), zero-copy `buffer=` imports, shared-memory
  views, and the `readonly` flag with its `TypeError`-on-write
  behavior. v0.1 construction always yields owned, mutable storage.
- **File operations**: `tofile`/`fromfile` (beyond what byte
  conversion already covers via plain files).
- **Pack/unpack utilities**: `pack()` (bytes→bits mapping) and
  `unpack()` with custom single-byte maps. (Not bit-packing; still
  deferred as edge API surface.)
- **Sorting** (`sort()`): trivial count-and-fill, but no v0.1
  workload or benchmark needs it.
- **`bitarray.util`**: `int2ba`/`ba2int`/`hex2ba`/`ba2hex`,
  `zeros`/`ones`/`urandom`/`random` builders, `serialize`/
  `deserialize`, `strip`, `subset`, `count_and/or/xor`,
  `huffman_code`, RLE/sparse helpers.
- **`bitarray.bitfields`**: struct-like `compile`/`pack`/`unpack`/
  `calcsize`.
- **Prefix-code machinery**: `encode`, `decode`/`decodeiterator`,
  `decodetree`, `canonical_huffman`.
- **Advanced utilities**: `sum_indices`, `intervals`, `pprint`,
  `xor_indices`, `correspond_all`, `byteswap`, `gen_primes`.

Rationale: none of these changes core storage semantics; several
(`util`, `bitfields`) are pure-Python orchestration that a native
port can consume unchanged or reimplement later. Deferring them keeps
v0.1's verification surface (goldens, differential tests,
benchmarks) proportional to the core.

## Category C — out of scope (unchanged)

- **`normalized_*`-style conveniences**: N/A here, but by analogy —
  anything not present in the reference package must not be invented
  (e.g. no NumPy-style ufunc surface).
- **Jaro-style analogues**: there are none in this domain; stated for
  completeness — do not add similarity metrics (Levenshtein-adjacent
  ideas belong to that library, not here).
- **Memory-mapped files**: buffer import covers the mechanism in the
  reference; OS-level mmap management is out of scope.
- **Thread-safety guarantees beyond the GIL-free build**: the
  reference advertises free-threaded support; a v0.1 Mojo port
  documents single-owner semantics and revisits only with demand.
- **Pickling**: Python-object serialization of the Mojo type is a
  binding concern, deferred with Python bindings generally.

## Resolved decisions (Phase 0 finalization)

1. **`frozenbitarray` is deferred in full.** No read-only flag, no
   attempt to reproduce Python subclassing, no `__hash__` on the v0.1
   type. The core struct stays extensible (endian flag plus buffer
   and length are all the state an immutable variant needs), but no
   immutable code path ships in v0.1.
2. **Sorting is deferred.** It is three lines given `count`, which is
   precisely why it can wait: it adds API surface without changing
   any storage or algorithm decision.
3. **Bytes construction means owned copies.** v0.1 `bitarray(b"...")`
   imports raw bytes into owned, mutable storage. Anything involving
   shared memory (buffer export, zero-copy views, `readonly` writes
   raising `TypeError`) is deferred with buffer-protocol interop.

## Scope trade-offs

- **Breadth vs. verifiability**: every included operation must be
  pinned by goldens, differential tests, *and* benchmarks. The
  deferred list is exactly the set whose edge cases would double the
  compat surface without changing the storage design.
- **Owned vs shared memory**: v0.1 never aliases external buffers.
  This removes the entire `readonly`/`exports`/`imported` state space
  (probed: `BufferInfo` carries `readonly`, `imported`, `exports`
  flags) at the cost of one copy on bytes construction — the right
  trade for a first verified port.
- **Read surface is complete, write surface is minimal**: all
  read/query paths (`count`, `find`, `search`, comparisons,
  conversions) ship so behavior is fully observable; deferred items
  are writers/transforms (`sort`, file I/O, codecs) or separate
  types (`frozenbitarray`).
- **No performance-driven scope**: nothing was included or excluded
  to make benchmarks look good. The deferred items include both fast
  paths (`sort`) and slow ones (`search` stays, and it is the
  expensive outlier), chosen on architectural separability instead.
