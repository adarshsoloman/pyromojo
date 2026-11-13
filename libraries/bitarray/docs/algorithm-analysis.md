# Algorithm analysis: bitarray internals and Mojo mapping

All reference facts below are from the C source (`bitarray.h`) or
verified by black-box probing (`experiments/`). Mojo feasibility notes
cite the Phase 0 toolchain probes in
`experiments/toolchain_validation/bitarray/`.

## 1. Storage model

- Contiguous `UInt8` buffer, `ceil(n/8)` bytes for `n` logical bits.
  Mojo equivalent: `List[UInt8]` with explicit length tracking —
  validated (`storage.mojo`: capacity/length independence, growth,
  indexed read/write, sub-range copy).
- Logical index `i` lives in byte `i // 8`; within the byte the bit
  position is `i % 8` (little-endian) or `7 - (i % 8)` (big-endian).
  This is the exact reference `BITMASK` rule, confirmed by round-trip
  probes against `tobytes()` outputs.
- Pad bits (trailing bits of the last byte beyond `n`) exist in
  storage but are outside the logical sequence. The reference zeroes
  them on read paths (`zlc`/`zlw` helpers); a Mojo port must do the
  same before any word-wide read, or comparisons and popcounts will
  see garbage.
- `nbytes`, `padbits`, `endian` are O(1) metadata, not computation.

## 2. Word-level bitwise operations

- AND/OR/XOR/NOT over whole `uint64_t` words, then a masked tail word.
  The reference casts the byte buffer to 64-bit words (`WBUFF`) and
  copies unaligned tails rather than requiring alignment — a Mojo port
  does the same with `List[UInt8]` segments or explicit loads.
- Validated in Mojo (`words.mojo`): `& | ^ ~` match C truth tables;
  per-word results compose by concatenation.
- Unequal lengths are a hard error in the reference (no padding,
  no truncation). A port must reproduce the error, not pick a side.
- Cross-endianness bitwise ops are rejected (`ValueError`); the port
  must check endianness flags before touching data, exactly as probed.

## 3. Shifts

- Shifts **preserve length** (`'10110011' << 1` is `'01100110'`);
  bits fall off, zeros fill in. Shift amount may exceed the length
  (result: all zeros); negative shifts raise.
- Decomposition for a native port: whole-word shift by `k // 64`
  words plus a bit-shift by `k % 64` with cross-word carry — the same
  block structure as the Phase 0 Myers probes. Amounts must be
  range-checked: Mojo full-width shifts are target-defined
  (probed: constant `<< 64` is a compile error; runtime `1 << 64`
  folds to `1`), so shift-by-`>=64` must be an explicit branch that
  yields zero, never a raw shift.
- Different lengths never arise (shift preserves length), so no
  padding rule is needed.

## 4. Population count

- No builtin exists in Mojo 1.2.0's `std` (`std.bit` has no
  `popcount`; `UInt64` has no `count_ones` — both verified missing).
- Validated alternatives (`words.mojo`): 4-line SWAR and a 16-entry
  nibble table agree on adversarial inputs (0, MAX, alternating,
  single-bit); both compose across words for multi-word counts.
- Recommendation: SWAR as the default (branchless, no table), with
  the nibble table kept as the test oracle — mirroring the DP-vs-
  bitparallel oracle pattern from the Levenshtein port.

## 5. Search (`find`/`index`/`search`, `count` with patterns)

- `find`/`index` locate the first match (or raise / return -1);
  `search` lists all match offsets; `right=1` variants scan from the
  right. All accept a bit or a sub-bitarray plus optional bounds.
- Naive cost is O(n·m); the reference is fast in practice (~ms at
  1M bits for `search`, ~µs for word-parallel `count`). A v0.1 Mojo
  port should implement the straightforward scan first (correctness
  over cleverness), with memchr-style word skipping as a documented
  follow-up — not in v0.1 scope.
- No partial-match state is exposed; each call is self-contained.

## 6. Resize, copy, slice, concat

- Growth is amortized; `clear()` resets length but keeps the buffer.
- Slice assignment **resizes** like Python `list` (verified:
  mismatched lengths legal). Slicing by steps/negative bounds follows
  sequence semantics on logical indices.
- `extend` with self as argument works (appends a snapshot).
- `repeat` by negative int yields empty (no error).
- Copy (`copy()`, `deepcopy`, explicit constructor) is independent;
  aliasing is never observable. A Mojo port with value-type buffers
  gets this naturally but must test it (reference has explicit tests).
- `insert(-1, …)` inserts before the last element (Python-list
  semantics); out-of-range positive index appends (verified).

## 7. Serialization and byte interop

- `tobytes` emits `ceil(n/8)` bytes with stored pad bits;
  `frombytes` appends whole bytes (caller trims to length).
  `tofile`/`fromfile(n)` move bytes; `n` counts bytes, not bits.
- Buffer protocol: export exposes the raw buffer; import from
  read-only sources (`bytes`) yields a read-only bitarray whose
  mutations raise `TypeError`.
- `bytereverse` (C-level) and `util.byteswap` are in-place and
  return `None` — callers must not chain on the result.
- `pack`/`unpack` are **not** bit-packing: each byte maps to one bit
  (`0x00`→0, else 1) and vice versa with configurable single-byte
  maps. Do not confuse with `tobytes`.
- Endianness only affects within-byte bit order on the wire; the
  byte stream order is always ascending.

## 8. What the algorithms imply for a Mojo port

- Core data structure: `List[UInt8]` buffer + `Int` length +
  endianness flag. All Phase 0 storage primitives validate.
- Hot loops are word-at-a-time over `UInt64` with masked tails;
  the only arithmetic hazards are silent wraparound (carry/borrow
  must be explicit, as in the Myers probes) and full-width shifts
  (branch instead of shifting).
- The natural v0.1 algorithm set is O(n/64) per op with O(1)
  setup — no algorithmic novelty required, only exact edge handling
  (empty, 1-bit, non-multiple-of-8/64 lengths, cross-endianness
  rejection, error parity).
- The expensive outlier is pattern search; everything else is
  memory-bandwidth-bound, which sets up the benchmark design.
