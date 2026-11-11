# MessagePack batch protocol (v0.1)

The native CLI and the Python compatibility suite speak a small binary
request/response protocol over stdin/stdout. It exists so the Python reference
can drive the same process model the final encoder/decoder will use without
`ctypes`, `PythonModuleBuilder`, or Python-specific object hooks.

Phase 1 implements framing, `PING`, and `ECHO`; `DECODE` and `ENCODE` return
`UNIMPLEMENTED` until the codec lands.

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
| `0x10` | `DECODE`  | Unimplemented     | MessagePack bytes | Decoded value model (Phase 2) |
| `0x11` | `ENCODE`  | Unimplemented     | Value model (Phase 2) | MessagePack bytes |

An empty body has no opcode and returns an `ERROR` frame.

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
- **Valid but unimplemented opcode**: the process answers with `UNIMPLEMENTED`
  and keeps reading.

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

## Build and run

```bash
.venv/bin/mojo build libraries/msgpack/mojo/cli.mojo \
  -I libraries/msgpack/mojo -o build/msgpack_cli
printf '\x00\x00\x00\x01\x01' | ./build/msgpack_cli | xxd
```
