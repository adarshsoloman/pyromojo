# Intel/DVI ADPCM (Phase 8)

Port of CPython 3.12.3 `audioop.lin2adpcm` / `audioop.adpcm2lin`
(`mojo_audioop/adpcm.mojo`). The code originates from the classic
Intel/DVI ADPCM implementation (via Sun's public-domain `g711.c`
derivations used by the SoX source CPython embeds).

## Algorithm (exact, source-derived)

Shared tables:

- **Index adjustment table** (16 entries):
  `{-1, -1, -1, -1, 2, 4, 6, 8, -1, -1, -1, -1, 2, 4, 6, 8}`.
- **Step-size table** (89 entries): `7, 8, 9, 10, …, 32767` (the classic
  IMA/DVI table).

### Encoder `lin2adpcm(fragment, width, state)`

Validation order: width + fragment alignment
(`audioop_check_parameters`), then state. `state=None` → predictor 0,
index 0; a non-tuple state raises `TypeError state must be a tuple or
None` (reference-only; the CLI state block is structural); predictor
outside [-32768, 32767] or index outside [0, 88] → `ValueError bad
state`.

Per sample (all widths read at the 32-bit position then shifted right
by 16: width 1 ×256, width 2 unchanged, width 3 `>>8`, width 4 `>>16`):

1. `diff` and `sign` (bit 3) from the difference against the predictor.
2. Quantize: `delta` bits 4/2/1 with `vpdiff = step>>3 + step + step>>1
   + step>>2` terms (the approximate `(delta+0.5)*step/4`).
3. Update the predictor with the **reconstructed** `vpdiff` (not the
   input sample), clamped to [-32768, 32767].
4. `index += indexTable[delta|sign]`, clamped to [0, 88];
   `step = stepsizeTable[index]`.
5. Nibble packing: **high nibble first**; the first sample of a pair
   fills the high nibble, the second is emitted as a byte. An **odd
   trailing sample updates the state but its nibble is dropped**
   (output length `len / (width*2)` bytes).

Returns `(bytes, (valpred, index))`; empty input returns the state
unchanged.

### Decoder `adpcm2lin(fragment, width, state)`

Validates the **width only** (any input byte length). Each byte yields
two samples, **high nibble first**. Per nibble: index update and clamp,
sign/magnitude split, `vpdiff` reconstruction, predictor update and
clamp, then `step = stepsizeTable[index]`. The output sample is
`valpred * 2^16` stored through the top-aligned shift (`valpred >> 8`
at width 1, `valpred` at width 2, `valpred << 8` at width 3,
`valpred << 16` at width 4). Two output samples per input byte.

## State

State is the pair `(valpred, index)` — the 16-bit predictor and the
step-size index (0–88). The same structure serves both operations, so
an encoder's state cannot be fed to a decoder (different algorithms,
but the same tuple shape). State round-trips through the CLI.

## Chunk-boundary behavior (verified against the reference)

- **Encoder, even-sized chunks**: concatenating outputs equals the
  whole encoding, and the final state matches (each call starts its
  nibble buffer fresh, which aligns when every chunk holds an even
  number of samples).
- **Encoder, odd-sized chunks**: concatenation is NOT byte-equal to the
  whole encoding. Each call drops its own odd trailing nibble and the
  next call starts a fresh buffer, so e.g. `[1,2,3,4]` encodes to 2
  bytes whole but 1 byte + 0 bytes as 3+1 chunks (both leave the same
  state progression). This is documented CPython behaviour, not a bug.
- **Decoder**: chunks of any size compose exactly (nibble pairing never
  crosses a call boundary).

## Port policies

No undefined behaviour is involved; all arithmetic is integer and
reproduced exactly. The reference-only state errors (`TypeError state
must be a tuple or None`, per-function `lin2adpcm()/adpcm2lin():
illegal state argument` prefixes) are not reachable through the CLI's
structural state block; the port API's `AdpcmState` cannot be
malformed.

## CLI opcodes

| Opcode | Request payload | Response payload |
| --- | --- | --- |
| `0x3A` lin2adpcm | `uint8 width \| uint8 has_state \| [int64_be valpred \| int64_be index] \| fragment` | `uint32_be out_len \| packed bytes \| int64_be valpred \| int64_be index` |
| `0x3B` adpcm2lin | same payload format | decoded fragment bytes + state |

## Tests

- Native: `tests/mojo/test_adpcm.mojo` — 11 tests (both ops, all
  widths, nibble sweep, packing, odd-sample dropping, clamping, state
  reuse, chunk composition for both ops, validation).
- Python compatibility: `test_adpcm_cli.py` (11 framing/protocol tests
  incl. state round-trips and chunk composition), `test_adpcm_oracle.py`
  (curated + randomized differential, seed `20260610`, exhaustive
  256-byte decoder group, chunk-composition group),
  `test_adpcm_vectors.py` (golden-vector replay).
- Golden vectors: 325 `p8-` cases (bundle now 1277): encoder at every
  width with boundaries/alternating/abrupt/repeated/continued-state
  and all error paths; decoder with all 256 byte values, all 16
  nibbles, sampled widths 1/3/4, continued/custom states, and errors.

## Remaining unimplemented operations

None — this completes the 26-operation audioop v0.1.0 API.
