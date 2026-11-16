# Audioop CLI opcode registry

Authoritative mapping of every opcode accepted by
`libraries/audioop/mojo/cli.mojo`, verified against
`mojo/mojo_audioop/protocol.mojo` and the `main()` dispatch (26
operation opcodes, each dispatched exactly once, plus the four
infrastructure opcodes).

Framing (unchanged since Phase 1): every request is
`uint32_be length | body`, every response is
`uint32_be length | uint8 status | payload` with `0` = OK, `1` =
error. Errors are returned as `STATUS_ERROR` frames; truncated headers
and over-64-MiB frames terminate the connection with a non-zero exit.

## Infrastructure opcodes

| Opcode | Name | Request payload | Response payload |
| --- | --- | --- | --- |
| `0x01` | PING | — | empty OK |
| `0x02` | ECHO | arbitrary bytes | same bytes |
| `0x20` | decode fragment | `uint8 width \| fragment` | space-separated ASCII decimals |
| `0x21` | encode fragment | `uint8 width \| space-separated ASCII decimals` | native-order fragment |

## Audioop operations (`0x22`–`0x3B`)

| Opcode | Operation | Request payload | Response payload |
| --- | --- | --- | --- |
| `0x22` | `add` | `uint8 width \| uint32_be len1 \| fragment1 \| fragment2` | fragment bytes |
| `0x23` | `bias` | `uint8 width \| int64_be bias \| fragment` | fragment bytes |
| `0x24` | `mul` | `uint8 width \| 8-byte IEEE-754 BE factor \| fragment` | fragment bytes |
| `0x25` | `reverse` | `uint8 width \| fragment` | fragment bytes |
| `0x26` | `byteswap` | `uint8 width \| fragment` | fragment bytes |
| `0x27` | `lin2lin` | `uint8 width \| uint8 newwidth \| fragment` | fragment bytes |
| `0x28` | `getsample` | `uint8 width \| int64_be index \| fragment` | one ASCII decimal |
| `0x29` | `max` | `uint8 width \| fragment` | one ASCII decimal (may exceed int32) |
| `0x2A` | `minmax` | `uint8 width \| fragment` | `min max` as two ASCII decimals |
| `0x2B` | `avg` | `uint8 width \| fragment` | one ASCII decimal |
| `0x2C` | `rms` | `uint8 width \| fragment` | one ASCII decimal (may exceed int32) |
| `0x2D` | `cross` | `uint8 width \| fragment` | one ASCII decimal |
| `0x2E` | `avgpp` | `uint8 width \| fragment` | one ASCII decimal |
| `0x2F` | `maxpp` | `uint8 width \| fragment` | one ASCII decimal |
| `0x30` | `findmax` | `int64_be length \| fragment` | index as one ASCII decimal |
| `0x31` | `findfactor` | `uint32_be len1 \| frag1 \| frag2` | 8 big-endian IEEE-754 bytes |
| `0x32` | `findfit` | `uint32_be len1 \| frag1 \| frag2` | ASCII decimal index, one space, 8 IEEE-754 bytes |
| `0x33` | `tomono` | `uint8 width \| 8-byte BE lfactor \| 8-byte BE rfactor \| fragment` | fragment bytes |
| `0x34` | `tostereo` | same as `0x33` | fragment bytes, left sample first |
| `0x35` | `ratecv` | `uint8 width \| int64_be nchannels \| int64_be inrate \| int64_be outrate \| int64_be weightA \| int64_be weightB \| uint8 has_state \| [int64_be d \| nchannels × (int64_be prev \| int64_be cur)] \| fragment` | `uint32_be out_len \| output bytes \| int64_be d \| nchannels × (int64_be prev \| int64_be cur)` |
| `0x36` | `lin2alaw` | `uint8 width \| fragment` | one A-law byte per sample |
| `0x37` | `alaw2lin` | `uint8 width \| codeword bytes` | `width` bytes per input byte (any byte length) |
| `0x38` | `lin2ulaw` | `uint8 width \| fragment` | one mu-law byte per sample |
| `0x39` | `ulaw2lin` | `uint8 width \| codeword bytes` | `width` bytes per input byte (any byte length) |
| `0x3A` | `lin2adpcm` | `uint8 width \| uint8 has_state \| [int64_be valpred \| int64_be index] \| fragment` | `uint32_be out_len \| packed bytes \| int64_be valpred \| int64_be index` |
| `0x3B` | `adpcm2lin` | same payload as `0x3A` | decoded fragment bytes + state (two samples per input byte) |

Notes and deliberate deviations from a uniform shape:

- `findmax` carries no width byte: the reference API is fixed 16-bit
  (`findmax(fragment, length)`), so there is no width to transmit.
- Decoders (`alaw2lin`, `ulaw2lin`, `adpcm2lin`) require no fragment
  alignment; the reference never checks it for these operations.
- Malformed requests produce error frames with the messages listed in
  the per-phase docs (e.g. `ratecv request too short: need width and
  two factors` for truncated fixed headers); truncated frame headers
  and frames over 64 MiB are fatal.
- Unknown opcodes return `unknown opcode N` and processing continues
  with the next frame; an empty frame returns `empty request frame`.
