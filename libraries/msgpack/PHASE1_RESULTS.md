# MessagePack Phase 1 results

Phase 1 established the reference, the golden-vector pipeline, the native value
model with depth safety, and the batch CLI framing. The encoder and decoder
themselves remain Phase 2 work.

## Environment

- Mojo 1.2.0 (`2016d0cd`), invoked as `.venv/bin/mojo`
- Python 3.13.14, `uv` 0.12.5
- Reference: `msgpack==1.2.4` (C extension present)
- Installation: `uv sync --extra dev` (pytest and ruff live in the `dev`
  optional-dependency group; `msgpack==1.2.4` is pinned in both
  `pyproject.toml` and `python_reference/requirements.txt`)

## Artifacts

| Path | Purpose |
|------|---------|
| `python_reference/generate_vectors.py` | Deterministic generator for the JSON bundle and Mojo case module; `--check` fails on drift |
| `python_reference/probe_reference_depth.py` | Per-depth reference probe in isolated subprocesses |
| `tests/vectors/msgpack_vectors.json` | 76 golden cases (1.1 MB) |
| `tests/mojo/generated_vectors.mojo` | Typed case metadata and lazy `Value` builders (1.2 MB) |
| `shared/test_vectors/schema/msgpack_vectors.schema.json` | Published JSON Schema for the bundle |
| `shared/validation/msgpack_vectors.py` | Standard-library structural validator used by pytest |
| `mojo/mojo_msgpack/value.mojo` | Tagged value model, explicit `Deinitable`, depth guard |
| `mojo/mojo_msgpack/protocol.mojo` | Big-endian length framing and opcode constants |
| `mojo/cli.mojo` | Batch CLI (`PING`, `ECHO`, `DECODE`/`ENCODE` as `UNIMPLEMENTED`) |
| `docs/batch_protocol.md` | Wire protocol specification |
| `tests/mojo/test_depth.mojo` | Depth, copy, move, and destruction tests |
| `tests/mojo/test_generated_vectors.mojo` | Generated-module consistency tests |

## Golden vectors

- 76 cases across nil, bool, integers, floats, strings, binary, arrays, maps,
  ext types, timestamps, and errors.
- All required markers are covered: fixint families; uint8/16/32/64;
  int8/16/32/64; float32/64; fixstr/str8/16/32; bin8/16/32;
  fixarray/array16/array32; fixmap/map16/map32; fixext1/2/4/8/16;
  ext8/16/32; timestamp32/64/96.
- `str32`, `bin32`, `ext32`, `array32`, and `map32` cases carry at least 65,536
  payload bytes. Large repeats use a compact `repeat` model in JSON and are
  expanded only when replaying.
- Map order and duplicate keys are preserved through an ordered-pair model;
  array keys and duplicate keys are covered as decode-only reference cases.
- Roundtrip cases re-encode against `msgpack==1.2.4` and must match the committed
  bytes exactly; decode/error cases replay against the reference.
- `test_committed_artifacts_are_current` runs `generate_vectors.py --check`.

### Reference depth probe

Probe source: `python_reference/probe_reference_depth.py`. Observed behavior:

| Depth | Reference C pack | Reference C unpack | Pure-Python pack | Pure-Python unpack |
|------:|------------------|--------------------|------------------|--------------------|
| 64 | ok | ok | ok | ok |
| 128 | ok | ok | ok | ok |
| 129 | ok | ok | ok | ok |
| 1000 | ok | ok | `RecursionError` | `StackError` |
| 1024 | ok | ok | `RecursionError` | `StackError` |
| 1025 | `ValueError: recursion limit exceeded` | `StackError` | `RecursionError` | `StackError` |
| 5000 | `ValueError` | `StackError` | `RecursionError` | `StackError` |
| 100000 | `ValueError` | `StackError` | `RecursionError` | `StackError` |

The C reference accepts exactly 1024 nested containers and rejects 1025. The
pure-Python fallback fails at roughly the interpreter recursion limit (1000).
PyroMojo's default `DEFAULT_MAX_DEPTH = 128` is deliberately more conservative
than either and is enforced by `Value.check_depth`.

Phase 0 measured the Mojo limits that motivate the guard: walking is safe at
200k, deep copy succeeds at 50k but segfaults at 75k, and recursive destruction
succeeds at 100k but segfaults at 200k.

## Batch CLI

Wire format: `uint32_be length | uint8 status/opcode | payload`; maximum body
64 MiB; clean EOF exits 0; framing errors return one `ERROR` frame, a stderr
diagnostic, and a non-zero exit. See `docs/batch_protocol.md`.

Phase 1 has no request ids, so the Nth response corresponds to the Nth request.
`ECHO` is binary-safe and writes stdout in 4 KiB chunks. Diagnostics never
share stdout with frames.

## Verification

```text
$ .venv/bin/pytest -q
21 passed

$ ./build/test_depth
8 tests run: 8 passed

$ ./build/test_generated_vectors
8 tests run: 8 passed

$ .venv/bin/ruff check libraries shared scripts
All checks passed!

$ .venv/bin/ruff format --check libraries shared scripts
17 files already formatted

$ .venv/bin/python libraries/msgpack/python_reference/generate_vectors.py --check
vectors: 76 cases, committed artifacts are current
```

The bundle also validates against the published Draft 2020-12 schema with
`jsonschema.Draft202012Validator` (one-off check; `jsonschema` is not a project
dependency).

CLI byte-level cases covered by pytest: PING, binary-safe ECHO (1 MiB),
pipelined frames, clean EOF, empty body, unknown opcode, `DECODE`/`ENCODE`
unimplemented, truncated header, truncated body, oversize length, and a valid
frame followed by a framing error.

## Known limitations and Phase 2 inputs

- No encoder or decoder yet; `DECODE`/`ENCODE` return `UNIMPLEMENTED`.
- `check_depth` validates after construction. The Phase 2 parser should guard
  depth incrementally so hostile input is rejected before building a deep tree.
- Mojo `main` exposes only 0/1 exit status; framing failures exit 1 with a
  stderr diagnostic.
- Generated Mojo repeat builders for the 65,536-element vectors are heavy to
  materialize (about 10 s across the whole suite). Keep large values lazy and
  do not add more large repeat cases without need.
- The Python fallback packer is not used by generated vectors; the C reference
  is authoritative.
