# Phase 0 toolchain validation — msgpack

Date: 2026-11-11
Compiler: Mojo 1.2.0 (2016d0cd) at `.venv/bin/mojo`
Python: 3.13.14
Host: Linux x86_64

Build pattern for every probe:

```bash
.venv/bin/mojo build <probe>.mojo -o /tmp/<probe>
/tmp/<probe>
```

All probes are self-checking and call `assert`; a probe is only PASS if it exits 0.
The EXIT column is the real process exit code.

| Probe | Covers | EXIT | Verdict |
|---|---|---|---|
| `recursive_value.mojo` | nested `Value`, copy, move, destruction | 0 | PASS |
| `float_bits.mojo` | f64/f32/int bit patterns | 0 | PASS |
| `utf8.mojo` | UTF-8 validate/reject/lossy, byte access | 0 | PASS |
| `file_io.mojo` | binary read/write/seek, chunky reads | 0 | PASS |
| `cli_timing.mojo` | argv, monotonic clock | 0 | PASS |
| `test_api.mojo` | std.testing discovery, `assert_raises` | 0 | PASS |
| `deep_nesting.mojo` | recursion stack limits | 0 at 50k copy, 100k no-copy; 139 at 75k copy, 200k destroy | PASS with limits |

## 1. Recursive `Value`

Environment: `.venv/bin/mojo build recursive_value.mojo -o /tmp/recursive_value`

```
nesting: PASS (array depth 3, map depth 4)
copy: PASS (deep copy, no aliasing)
move: PASS (nested structure intact after transfer)
destruction: PASS (10,000 nested values constructed and dropped)
recursive_value: PASS
```

Verified type shape:

```mojo
struct Value(Deinitable, Copyable, Movable):
    var tag: UInt8
    var num: UInt64
    var kids: List[Self]

    def __deinit__(deinit self):
        pass  # fields are destroyed automatically after this body

    def __init__(out self, *, copy: Self):
        self.tag = copy.tag
        self.num = copy.num
        self.kids = List[Self](copy=copy.kids)
```

Critical finding: **the explicit `Deinitable` conformance is required.** Without it,
`List[Self]` is rejected:

```
error: field 'kids' has non-'Deinitable' type 'List[Value]'
```

`OwnedPointer[List[Self]]` fails the same way. Only a raw `Pointer` field compiles
(it breaks the trait cycle), but then every allocation, deep copy, and destroy is
manual. Explicit `Deinitable` + `List[Self]` is simpler and was used for the rest of
the probes.

Destructor semantics (confirmed with a `Drop` counter type): the user
`__deinit__` body runs **first**, then remaining fields are destroyed automatically.
Hence `pass` is correct and recursively destroys `kids`. No manual field teardown.

Copy and move semantics verified: `value.copy()` deep-copies nested lists (no
aliasing); `value^` transfers ownership and leaves the source unusable. Moves and
non-trivial copies must be explicit — implicit copies of `Value`/`List` are compile
errors.

## 2. Float and integer bit patterns

Environment: `.venv/bin/mojo build float_bits.mojo -o /tmp/float_bits`

```
f64 0.0 bits=0x0
f64 -0.0 bits=0x8000000000000000
f64 1.0 bits=0x3ff0000000000000
f64 -2.5 bits=0xc004000000000000
f64 max_finite bits=0x7fefffffffffffff
f64 inf bits=0x7ff0000000000000
f64 -inf bits=0xfff0000000000000
f64 nan bits=0x7ff8000000000001
f32 0.0 bits=0x0
f32 -0.0 bits=0x80000000
f32 1.0 bits=0x3f800000
f32 -2.5 bits=0xc0200000
f32 inf bits=0x7f800000
int: PASS (sign bit preserved through to_bits/from_bits)
float_bits: PASS
```

Verified API:

```mojo
var bits: UInt64 = UInt64(value.to_bits())      # to_bits() returns Scalar, not UInt64
var value = Float64(from_bits=bits)             # also Float32(from_bits=u32)
var signed_bits = UInt64(signed.to_bits())
var signed = Int64(from_bits=signed_bits)
```

Warnings for Phase 1:

- `std.memory.bitcast` is SIMD-only (`bitcast[dtype](val: SIMD[...])`). It does not
  accept scalar `Float64`/`UInt64`. Use `to_bits()` / `from_bits=`.
- `to_bits()` returns a `Scalar[...]`; wrap it explicitly (`UInt64(...)`,
  `UInt32(...)`) before storing.
- `let` is not a Mojo 1.2 keyword. Use `var` for every binding.
- `Float64.nan()` / `Float64.infinity()` do not exist; construct special values via
  `from_bits` or use checked math helpers.
- NaN payloads and signed zero round-trip exactly, which is what msgpack needs.

## 3. UTF-8 strings

Environment: `.venv/bin/mojo build utf8.mojo -o /tmp/utf8`

```
valid: A bytes= 1
valid: é bytes= 2
valid: € bytes= 3
valid: 😀 bytes= 4
valid:   bytes= 1
lone continuation rejected: Cannot construct a String from invalid UTF-8 data
lone continuation lossy: �
overlong NUL rejected: Cannot construct a String from invalid UTF-8 data
overlong NUL lossy: ��
truncated 3-byte rejected: Cannot construct a String from invalid UTF-8 data
truncated 3-byte lossy: �
UTF-16 surrogate rejected: Cannot construct a String from invalid UTF-8 data
UTF-16 surrogate lossy: ���
above U+10FFFF rejected: Cannot construct a String from invalid UTF-8 data
above U+10FFFF lossy: ����
unsafe_from_utf8: PASS
embedded NUL: PASS (byte_length 3)
utf8: PASS
```

Verified API:

```mojo
String(from_utf8=Span[Byte]) raises          # validates, then copies
String(unsafe_from_utf8=Span[Byte])          # no validation, copies
String(from_utf8_lossy=Span[Byte])           # U+FFFD substitution
s.as_bytes() -> Span[Byte]                   # borrowed view
s.byte_length() -> Int
```

Rejections tested: lone continuation (`80`), overlong NUL (`C0 80`), truncated
3-byte sequence (`E2 82`), UTF-16 surrogate (`ED A0 80`), code point above
U+10FFFF (`F4 90 80 80`). All raise `Cannot construct a String from invalid UTF-8
data`. Lossy conversion replaces each invalid byte with U+FFFD; the number of
replacement characters is per-byte here, so vectors must assert on the exact lossy
output produced, not assume one replacement per sequence.

Embedded NUL bytes are preserved (`byte_length == 3`). Decoder errors must map to
`raise Error(...)`, caught by the CLI harness and reported on stderr with a non-zero
exit.

## 4. Binary file I/O

Environment: `.venv/bin/mojo build file_io.mojo -o /tmp/file_io`

```
write: PASS (6 bytes incl 0x00, 0xFF, 0x80)
read_bytes(-1): PASS
read_bytes(size): PASS (2 + 2 + 2, then empty at EOF)
seek: PASS (offset 4 -> 2 bytes)
missing file rejected: Failed to open file '/tmp/pyromojo_phase0_missing_file.bin': No such file or directory
missing file: PASS
file_io: PASS
```

Verified API:

```mojo
var f = FileHandle(path: StringSlice, mode: StringSlice) raises
var all = f.read_bytes()            # size = -1 reads to EOF
var part = f.read_bytes(size=2)     # returns up to `size`; empty at EOF
f.write_all(payload)                # payload: Span[Byte]
var offset = f.seek(4)              # SEEK_SET by default
f.close()
```

`write_all` is a `Writer` method and accepts `Span[Byte]` directly from a
`List[UInt8]`. Opening a missing file raises with a descriptive message. This is
enough for the v0.1 CLI (`pack`/`unpack` read the whole file, no streaming).

## 5. CLI arguments and timing

Environment: `.venv/bin/mojo build cli_timing.mojo -o /tmp/cli_timing`
then `/tmp/cli_timing alpha beta`

```
argc: 3
argv[0]: /tmp/cli_timing
argv[1]: alpha
argv[2]: beta
checksum: 1499998500000
elapsed_ns: 20
ns_per_round: 0
cli_timing: PASS
```

Verified API: `std.sys.argv() -> Span[StaticString]`, `String(arg)` conversion,
`std.time.perf_counter_ns()`.

Caveat: a 1M-iteration arithmetic loop was constant-folded; 20 ns for 1M rounds is
not a measurement. Phase 1 benchmarks must time real encode/decode over
black-box payloads (values read from input, results written/checksummed), not
synthetic loops, and should cross-check with an external timer.

## 6. Test API

Environment: `.venv/bin/mojo build test_api.mojo -o /tmp/test_api`

```
Running 3 tests for .../test_api.mojo
    PASS [ 0.001 ] test_arithmetic
    PASS [ 0.001 ] test_assert_raises
    PASS [ 0.001 ] test_failure_is_attributed
--------
Summary [ 0.001 ] 3 tests run: 3 passed , 0 failed , 0 skipped
```

Verified pattern:

```mojo
from std.testing import TestSuite, assert_equal, assert_raises

def test_x() raises:
    assert_equal(2 + 2, 4)

def test_y() raises:
    with assert_raises(contains="boom"):
        raise Error("boom happened")

def main() raises:
    TestSuite.discover_tests[__functions_in_module()]().run()
```

Every test function must declare `raises`, because the assertion helpers raise.

## 7. Recursion limits (informs max-depth guard)

`deep_nesting.mojo` builds a left-deep chain of arrays and optionally deep-copies it.
It takes depth and an optional `nocopy` argument.

| Operation | Depth | Result |
|---|---|---|
| build + walk | 100,000 | PASS |
| build + walk | 200,000 | PASS (before destruction) |
| deep copy | 50,000 | PASS |
| deep copy | 75,000 | segfault (exit 139, stack in `List::__init__(copy)`) |
| deep copy | 100,000 | segfault (exit 139) |
| build + walk + drop | 100,000 | PASS |
| build + walk + drop | 200,000 | segfault during recursive destruction (exit 139, after walk PASS) |

Conclusion: recursive `Value` copy and destruction are native-stack bounded. Input
nesting is attacker-controlled, so the decoder **must** enforce a depth limit before
building or copying anything. Recommended: `max_depth = 1024` default, configurable
via CLI flag, well below the measured failure points. The encoder also walks and
destroys user-supplied trees recursively; document the same limit for encode or
reject deeper trees with a clear error.

## 8. API gotchas affecting Phase 1

- `list` has no variadic constructor. Use list literals (`[a, b]`) or
  `List[T](capacity=n)` plus `append`.
- `List`, `String`, and `Value` are not implicitly copyable. Use `.copy()` for an
  explicit deep copy, `^` to move.
- Out-parameters need `mut`: `def f(mut out: List[UInt64])`; callers pass `out`
  without `^`.
- `Span` is `std.collections.Span`; implicit conversion from `List[Byte]` works.
- Every fallible function (UTF-8 constructor, file I/O, `Error`) must declare
  `raises`; callers must use `try`/`except`.
- `hex()` already includes the `0x` prefix.
- Absolute `.venv/bin/mojo` avoids the stale system Mojo 1.0.0 on `PATH`.

## Phase 1 readiness

Approved design holds with one addition: recursive `Value` needs an explicit
`Deinitable` conformance, and a mandatory decoder depth guard. No architecture
change is required for the `Value` model, copy/move semantics, UTF-8 handling, file
I/O, CLI, or testing strategy.

Open item deferred to Phase 1: confirm the reference `msgpack==1.2.4` behavior for
deeply nested input (C extension) and align message text/exit codes for CLI
compatibility testing. The Mojo depth guard stays regardless, because crashing on
hostile input is not acceptable.
