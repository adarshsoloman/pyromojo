# Reference audit: `bitarray` 3.12.3

Pinned: `bitarray==3.12.3` (import name `bitarray`, Python ≥3.7,
`License-Expression: PSF-2.0`, no dependencies), installed ephemerally
into `.venv` via `uv pip install` for black-box observation only.
`pyproject.toml` and dependency files are untouched in Phase 0
(the formal pin belongs in `python_reference/requirements.txt`,
created when implementation begins).

## 1. Identity and license

- PyPI name and import name are both `bitarray`; latest stable at time
  of research is **3.12.3** (verified against the PyPI JSON API;
  `master` carries an unreleased `3.12.4` dev header — do not pin
  master, pin the release).
- License: **PSF-2.0** (Ilan Schnell variant, per METADATA and the
  repo LICENSE file: royalty-free use, modification, and
  redistribution with retained copyright notice). This is a permissive
  license: **no copyleft review is required** (contrast with the GPL
  oracle in the Levenshtein port). Vendoring is still out of scope —
  the C source (`_bitarray.c`, `_util.c`) is read for semantics only.
- Home: https://github.com/ilanschnell/bitarray, docs at
  https://bitarray.readthedocs.io/.
- Pure C implementation ("All functionality is implemented in C"),
  plus a small Python layer (`util.py`, `bitfields.py`) and type stubs
  (`__init__.pyi`, `util.pyi`). Test suite: 700+ unit tests
  (`test_bitarray.py` runs 723 tests, 0 failures in this build).

## 2. Memory representation (verified against C source + probes)

- The object header (`bitarrayobject` in `bitarray.h`) holds:
  `ob_item` (raw `char` buffer), `allocated` (buffer size **in bytes**),
  `nbits` (logical length **in bits**), `endian` flag, plus buffer-
  protocol bookkeeping (`ob_exports`, `imported`) and `readonly`.
- Packing: `BYTES(bits) = (bits + 7) >> 3`; `PADBITS = (8 - nbits % 8)
  % 8`. Allocation is byte-granular; the pad region exists in the
  buffer but is not part of the logical sequence.
- Per-bit access is `byte = buf[i >> 3]` with mask
  `1 << (i % 8)` (little-endian) or `1 << (7 - (i % 8))` (big-endian).
  Endianness therefore selects the **bit order within each byte**; byte
  order in memory is always ascending.
- Verified endianness mapping (`reference_probe_output.txt`):
  logical `11001010` is byte `0xCA` big-endian vs `0x53`
  little-endian; a lone `1` is `0x80` vs `0x01`.
- `buffer_info()` exposes `address, nbytes, endian, padbits, alloc,
  readonly, imported, exports`. `nbytes`/`padbits`/`endian` are plain
  attributes, not methods. `alloc` is allocated bytes (>= nbytes).
- No overallocation policy is documented; treat growth as amortized
  and measure, don't assume a factor.

## 3. Endianness semantics (probed)

- `get_default_endian()` is `'big'`; per-object `endian=` selects
  `'big'` or `'little'` (anything else raises `ValueError`).
- Comparisons (`==`, `<`, ...), concatenation, `+=`, and `extend`
  work **across** endiannesses by comparing/appending logical bits:
  `bitarray('101','big') == bitarray('101','little')` is `True`.
- Bitwise ops (`&`, `|`, `^`) and in-place variants **require equal
  endianness** and raise `ValueError: bitarrays of equal bit-endianness
  expected` otherwise. This is the one cross-endianness hard boundary.
- `tobytes()` output differs by endianness (same logical bits, mirrored
  bit positions); `frombytes` consumes raw whole bytes and appends
  them, so a non-multiple-of-8 stream must be trimmed by the caller.
- `byteswap` exists only as `bitarray.util.byteswap` (in-place, returns
  `None`); there is no `.byteswap()` method.

## 4. Core behavior inventory (all probed; see `experiments/`)

- **Indexing**: `a[i]`, negative indices, slices incl. steps and
  reversal; out-of-range raises `IndexError`. Assignment accepts only
  0/1 (else `ValueError`/`TypeError`); **slice assignment resizes**
  like `list` (mismatched lengths are legal).
- **Mutation**: `append`, `extend` (str/list/bitarray iterables; `int`
  rejected), `insert` (negative allowed; past-end appends),
  `pop`/`remove` (missing raises), `clear` (length 0, keeps buffer),
  `reverse` (in place), `setall`, `del a[i]`/`del a[i:j]`,
  `+`/`+=`/`*`/`*=` (repeat by non-negative int).
- **Queries**: `count(v[, start[, stop[, step]]])`, `find`/`index`
  (first match or `ValueError`; `find` missing returns -1),
  `search` (all match offsets, optional `right=1` for right-to-left),
  `all`/`any`, iteration yields Python `int`s, `in` accepts int or
  bitarray (a `str` raises `TypeError`), full ordering `<`/`<=`/`>`
  compared lexicographically (shorter-is-prefix sorts first).
- **Bitwise**: `& | ^ ~` plus in-place forms and `invert([i])`;
  unequal lengths raise `ValueError` (no implicit padding).
  **Shifts preserve length** (`'10110011' << 1` is `'01100110'`;
  bits fall off, zeros fill in); negative shift raises.
- **Sizes**: `len`, `nbytes` (= ceil(n/8)), `padbits`, `endian`,
  `fill()` (pads to a byte boundary with zeros, returns pad count),
  `sort()` (count-and-fill order), `rotate(k)` (right rotation by
  `k mod n`, negative rotates left), `copy`/`deepcopy` independent,
  `readonly` flag (set only by importing a read-only buffer; writes
  then raise `TypeError`).
- **Equality/hash**: `==` compares logical bits (endian-insensitive);
  non-bitarray operands are `False`/`TypeError` (no coercion);
  `bitarray` is unhashable, `frozenbitarray` is hashable.
- **Constructors**: from bit-string (whitespace/underscores allowed),
  int iterables, `bytes` (1 bit per byte, 0x00→0 else 1 — **not**
  bit-packing), `buffer=` (bytes/bytearray/memoryview; `bytes` imports
  read-only), `endian=` kwarg. `pack(bytes-like)` maps each byte to
  one bit; `unpack(zero=, one=)` maps each bit to a byte.
- **Interop**: `tobytes`/`frombytes`, `tofile`/`fromfile(n)` (n in
  bytes), buffer protocol export (bytes of the buffer) and import;
  `bytereverse` is in-place and returns `None`; partial trailing bytes
  retain pad bits as stored zeros.
- **`frozenbitarray`**: immutable, hashable subclass; mixed-endian and
  mixed-type concat rules: frozen+frozen→frozen, frozen+plain→frozen,
  plain+frozen→plain.
- **Errors**: `ValueError` for bad values/lengths/missing items;
  `IndexError` for out-of-range access and empty `pop`;
  `TypeError` for wrong operand types; `OverflowError` is *not*
  observed in normal operation (lengths are `Py_ssize_t`-bounded).

## 5. Sub-packages: `util` and `bitfields`

- `bitarray.util` (pure Python + C helpers): `int2ba`/`ba2int`
  (optional signed), `hex2ba`/`ba2hex`, `zeros`/`ones`,
  `urandom`/`random`/`random_k`/`random_p`, `serialize`/
  `deserialize` (length-prefixed), `strip` (default right),
  `subset` (bool), `count_and/or/xor`, `huffman_code` (+
  `canonical_huffman`), `sc_encode`/`sc_decode`,
  `vl_encode`/`vl_decode`, `rle`-family helpers. These are
  orchestration conveniences over the core, not core semantics.
- `bitarray.bitfields` (pure Python, stdlib-only): struct-like
  `compile()`/`pack()`/`unpack()`/`calcsize()` for fixed-width
  bit-field structures. Depends only on the public bitarray API.
- `decodeiterator`/`decodetree` support prefix-code decoding;
  `decode()` returns an iterator.

## 6. Reference-performance notes (for benchmark design)

Single-process min-of-N timings on this machine (Ryzen 7 6800H,
CPython 3.13): bitwise AND over 1M random bits ≈ 5 µs; `count()` ≈
24 µs regardless of content; `tobytes` ≈ 2 µs; LCS-style `search`
≈ 6.7 ms at 1M bits (the expensive path). Sub-microsecond timings at
small sizes need min-of-N reporting. (Feasibility numbers only — not
published results.)
