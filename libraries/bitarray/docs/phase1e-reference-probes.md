# Phase 1E reference probes: `tobytes`, `frombytes`, bytes construction

Pinned oracle: `bitarray==3.12.3`. Every claim below was observed by
direct black-box probing (see `tests/python_compat/test_serialization_oracle.py`,
which encodes the same expectations as executable tests).

## 1. `tobytes()` — packed, endian-aware, independent, zero-padded

- Signature `tobytes()`, no arguments; returns `bytes` (immutable).
- Big-endian packs MSB-first: `"10110011"` → `b"\xb3"`.
  Little-endian packs LSB-first: `"10110011"` → `b"\xcd"`.
- Partial final bytes are zero-padded in the pad region: big `"10110"`
  → `b"\xb0"` (`10110000`); little `"10110"` → `b"\x0d"`
  (`00001101`, pad bits are the top three zeros).
- Empty array → `b""`.
- The returned object is independent: mutating a `bytearray` copy of it
  leaves the source bitarray unchanged (and `tobytes()` never mutates
  the source).

## 2. `frombytes()` — appends whole bytes, keeps endianness

- Signature `frombytes(bytes-like)`; returns `None`.
- **Appends** (never replaces): `"1" + b"\xca"` → `"111001010"` (1 + 8
  bits); `"101" + b"\xca"` → `"10111001010"`.
- Each appended byte contributes 8 logical bits read in the **target's**
  endianness: little-endian `"101" + b"\xca"` (LSB-first `01010011`)
  → `"10101010011"`. The existing endianness is preserved.
- Works from any starting alignment, including non-byte-aligned
  (`"101"` + 1 byte → 11 bits) and empty (`"" + b"\xca"` → 8 bits,
  `"101" + b""` unchanged). Multiple consecutive calls accumulate.
- Accepts `bytes`, `bytearray`, `memoryview`; `str`/`int` and other
  types → `TypeError: a bytes-like object is required, not ...`.
- Mojo mapping: `frombytes(data: List[UInt8])`. Non-byte-like inputs
  cannot reach the overload (static equivalent of `TypeError`).

## 3. Construction from bytes — packed import, owned copy

- `bitarray(b"\x01\x00\x02")` yields 24 bits (`00000001 00000000
  00000010`): each byte is imported as 8 packed bits, MSB-first within
  the byte for big-endian (`00000001`) and LSB-first for little-endian
  (`bitarray(b"\x01\x00", endian="little")` → `"1000000000000000"`).
- `bytearray` inputs behave identically; `b""` yields an empty array.
- This is the "raw packed import into owned, mutable storage" the
  frozen v0.1 scope describes. The Mojo port does NOT add a separate
  constructor: the Phase 1A packed-buffer constructor
  `BitArray(buffer, length, big_endian)` (exact-size buffer, padding
  normalized) is that path; callers pass `buffer.copy()` for
  copy-in semantics. No new API is introduced for it.

## 4. Framed protocol decisions (project-level, not reference behavior)

The logical bit length can never be inferred from packed bytes (one
byte may carry 1–8 logical bits), so the frame carries it explicitly,
per the Phase 0 wire-format decision (explicit packed bytes + `nbits`
+ `endian`; pad bits ignored-on-read, zeroed-on-write):

- Canonical payload: `uint32_be nbits | uint8 endian_id | packed bytes`
  with `0x00` = big, `0x01` = little, and exactly `ceil(nbits/8)` data
  bytes. Pad bits MUST be zero on the wire.
- CLI opcodes mirror the MessagePack numbering: `0x10` decode
  (payload → `to01` ASCII), `0x11` encode (endian byte + ASCII bits →
  canonical payload), with shared `0x01` ping / `0x02` echo and
  `0/1` ok/error statuses over the established
  `uint32 length | body` framing.
- Decoder validation order: payload length (≥5 bytes) → endian id →
  exact byte count → zeroed padding → construct + normalize.
  Violations are `STATUS_ERROR` frames; the decoder never exposes pad
  bits as logical data (nonzero pad is rejected, not normalized).
- Encode requests carry the bit sequence as ASCII (length is the
  string length, so no length field can disagree); decode responses
  return ASCII for the same reason. Length-bearing binary appears only
  in the canonical payload, where it is validated.
