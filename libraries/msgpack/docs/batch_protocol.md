# MessagePack batch protocol (v0.1)

The native CLI and the Python compatibility suite speak a small binary
request/response protocol over stdin/stdout. It exists so the Python reference
can drive the same process model the final encoder/decoder will use without
`ctypes`, `PythonModuleBuilder`, or Python-specific object hooks.

Phase 4 implements framing, `PING`, `ECHO`, and `DECODE`/`ENCODE` for integers,
Float32/Float64, strings, binary, and recursively nested arrays and maps.
Extensions and timestamps still return `UNIMPLEMENTED`; malformed wire data
and models return `ERROR`. Bare top-level nil and bool keep the Phase 1
`UNIMPLEMENTED` response; they are fully supported as array and map children.

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

| Opcode | Name      | Status in Phase 4 | Request payload | Success response payload |
|--------|-----------|-------------------|-----------------|--------------------------|
| `0x01` | `PING`    | Implemented       | Ignored         | Empty                    |
| `0x02` | `ECHO`    | Implemented       | Arbitrary bytes | Exact request payload    |
| `0x10` | `DECODE`  | Scalars, arrays, maps | MessagePack bytes | Value model |
| `0x11` | `ENCODE`  | Scalars, arrays, maps | Value model | MessagePack bytes |

An empty body has no opcode and returns an `ERROR` frame.

### Value transfer models

`DECODE` returns and `ENCODE` accepts one of these models. Scalar models are
unchanged from Phase 3:

```
integer := uint8 tag | uint64_be bits
tag     := 0x00 signed | 0x01 unsigned

float32 := 0x10 | 4 float bytes
float64 := 0x11 | 8 float bytes
string  := 0x12 | UTF-8 payload bytes
binary  := 0x13 | arbitrary payload bytes
```

Containers are recursive. Each child model is length-prefixed so the receiver
can frame and validate it before decoding:

```
array := 0x14 | uint32_be count | (uint32_be length | model) * count
map   := 0x15 | uint32_be pairs | key/value frames * pairs
key/value frame := uint32_be length | model

nil   := 0xc0
false := 0xc2
true  := 0xc3
```

`bits` is the two's-complement bit pattern for signed integers and the plain
64-bit value for unsigned integers. Float models carry the IEEE 754 bit
pattern, preserving NaN payloads and signed zero. String and binary lengths
come from the frame length; the string model must contain valid UTF-8. Map
models store key/value pairs in order and preserve duplicate keys; the map
length is the pair count.

Positive fixints and uint8/16/32/64 decode to tag `0x01`; negative fixints and
int8/16/32/64 decode to tag `0x00`. MessagePack has no independent signedness
bit for non-negative wire values, so a positive integer encoded from a signed
`Value` decodes back with the unsigned tag.

Unknown model tags are `ERROR`. Integer models must remain exactly 9 bytes;
float32 and float64 models must be exactly 5 and 9 bytes respectively. Bare
top-level `0xc0`/`0xc2`/`0xc3` models return `UNIMPLEMENTED` to preserve the
Phase 1 stub behaviour; the same bytes are valid as child models.

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
- **Valid but unimplemented input**: extension or timestamp values get
  `UNIMPLEMENTED` and the process keeps reading. Bare top-level nil and bool
  keep their Phase 1 `UNIMPLEMENTED` response.
- **Malformed or truncated input**: `ERROR` includes a category and
  byte offset, for example `truncated: offset 1`, `invalid-utf8: offset 1`,
  `invalid-marker: offset 0`, or `trailing-data: offset 3`.
- **Depth and resource limits**: nesting deeper than `max_depth`
  (default 128) or a declared item count above `max_container_items`
  (default 1,000,000) fails with `depth-exceeded` or `container-limit`
  respectively. Counts are checked against the remaining input before any
  allocation, so a declared 4-billion-item array costs one error, not a
  4-billion-element allocation.

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
`DECODE` of `92 01 c3` (`[1, true]`) returns
`14 00 00 00 02 00 00 00 09 01 <u64 1> 00 00 00 01 c3` (a 9-byte integer model
framed inside a 2-item array model); `ENCODE` of that model returns `92 01
c3`. `DECODE` of `81 a1 6b c0` (`{"k": nil}`) returns
`15 00 00 00 01 00 00 00 02 12 6b 00 00 00 01 c0`.

Nesting depth counts scalars as depth 1 and a container as one plus its
deepest child, so 127 nested arrays around a scalar is the deepest value at
the default limit of 128. Duplicate map keys decode as ordered pairs and
re-encode to identical bytes; Python `dict` cannot represent them (or
unhashable keys such as arrays), so Python-side reference code uses
`object_pairs_hook` and `strict_map_key=False`. The reference C extension
caps nesting at 1024, well above the native default of 128.

## Build and run

```bash
.venv/bin/mojo build libraries/msgpack/mojo/cli.mojo \
  -I libraries/msgpack/mojo -o build/msgpack_cli
printf '\x00\x00\x00\x01\x01' | ./build/msgpack_cli | xxd
```
