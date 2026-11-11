# MessagePack batch protocol (v0.1)

The native CLI and the Python compatibility suite speak a small binary
request/response protocol over stdin/stdout. It exists so the Python reference
can drive the same process model the final encoder/decoder will use without
`ctypes`, `PythonModuleBuilder`, or Python-specific object hooks.

Phase 3 implements framing, `PING`, `ECHO`, and `DECODE`/`ENCODE` for integers,
Float32/Float64, strings, and binary. Arrays, maps, extensions, timestamps,
nil, and bool still return `UNIMPLEMENTED`; malformed scalar models return
`ERROR`.

## Framing

All integers are big-endian. A frame is a 32-bit body length followed by the
body. The length counts body bytes only (everything after the length field).

```
request  := uint32_be length | body
body     := uint8 opcode | payload

response := uint32_be length | body
body     := uint8 status | payload
```

- `length` includes the opcode/status byte.
- Maximum body size is **64 MiB** (`MAX_FRAME_BYTES`). A larger declared length
  is a framing error and no body is read.
- Frames are processed strictly in order. There are no request ids; the Nth
  response belongs to the Nth request.
- Payloads are opaque bytes. They may contain NUL, invalid UTF-8, or any other
  binary data; nothing is text-decoded on the wire.

## Opcodes

| Opcode | Name      | Status in Phase 1 | Request payload | Success response payload |
|--------|-----------|-------------------|-----------------|--------------------------|
| `0x01` | `PING`    | Implemented       | Ignored         | Empty                    |
| `0x02` | `ECHO`    | Implemented       | Arbitrary bytes | Exact request payload    |
| `0x10` | `DECODE`  | Scalar types      | MessagePack bytes | Scalar model |
| `0x11` | `ENCODE`  | Scalar types      | Scalar model | MessagePack bytes |

An empty body has no opcode and returns an `ERROR` frame.

### Scalar transfer models

`DECODE` returns and `ENCODE` accepts one of these models. Integer models are
unchanged from Phase 2 and are exactly 9 bytes:

```
integer := uint8 tag | uint64_be bits
tag     := 0x00 signed | 0x01 unsigned

float32 := 0x10 | 4 float bytes
float64 := 0x11 | 8 float bytes
string  := 0x12 | UTF-8 payload bytes
binary  := 0x13 | arbitrary payload bytes
```

`bits` is the two's-complement bit pattern for signed integers and the plain
64-bit value for unsigned integers. Float models carry the IEEE 754 bit
pattern, preserving NaN payloads and signed zero. String and binary lengths
come from the frame length; the string model must contain valid UTF-8.

Positive fixints and uint8/16/32/64 decode to tag `0x01`; negative fixints and
int8/16/32/64 decode to tag `0x00`. MessagePack has no independent signedness
bit for non-negative wire values, so a positive integer encoded from a signed
`Value` decodes back with the unsigned tag.

Unknown model tags are `ERROR`. Integer models must remain exactly 9 bytes;
float32 and float64 models must be exactly 5 and 9 bytes respectively.

## Statuses

| Status | Name            | Meaning |
|--------|-----------------|---------|
| `0x00` | `OK`            | Operation completed; payload is the result. |
| `0x01` | `ERROR`         | Malformed request or unknown opcode; payload is a UTF-8 diagnostic. |
| `0x02` | `UNIMPLEMENTED` | Valid request for a feature not yet available; payload is a UTF-8 diagnostic. |

Diagnostics in response payloads are informational only; clients must key on
the status byte, not message text.

## Session termination

- **Clean EOF between frames** (stdin closes before a new length field): exit
  code `0`, no further output. A client may send zero or more frames and then
  close stdin.
- **Framing error** (partial header, partial body, body larger than the limit):
  one `ERROR` frame is written for the failed request, a diagnostic is written
  to stderr, and the process exits non-zero. Frames completed before the error
  are answered normally.
- **Unknown opcode / empty body**: the process answers with `ERROR` and keeps
  reading.
- **Valid but unimplemented input**: nil, bool, array, map, extension, or
  timestamp values get `UNIMPLEMENTED` and the process keeps reading.
- **Malformed or truncated scalar input**: `ERROR` includes a category and
  byte offset, for example `truncated: offset 1`, `invalid-utf8: offset 1`,
  `invalid-marker: offset 0`, or `trailing-data: offset 3`.

The framed stream is stdout only. Diagnostics never share stdout with frames;
stderr is free-form text.

## Examples

See the byte-level tests in
`tests/python_compat/test_cli_protocol.py` for the exhaustive cases. `PING` is:

```
request:  00 00 00 01  01
response: 00 00 00 01  00
```

and `ECHO "hi"` is:

```
request:  00 00 00 03  02 68 69
response: 00 00 00 03  00 68 69
```

`DECODE` of `cc ff` (unsigned 255) returns the model
`01 00 00 00 00 00 00 00 ff`; `ENCODE` of that model returns `cc ff`.
`DECODE` of `ca 3f c0 00 00` (Float32 1.5) returns `10 3f c0 00 00`;
`DECODE` of `a5 68 65 6c 6c 6f` (`"hello"`) returns `12 68 65 6c 6c 6f`.

## Build and run

```bash
.venv/bin/mojo build libraries/msgpack/mojo/cli.mojo \
  -I libraries/msgpack/mojo -o build/msgpack_cli
printf '\x00\x00\x00\x01\x01' | ./build/msgpack_cli | xxd
```
