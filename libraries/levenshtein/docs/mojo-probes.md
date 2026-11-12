# Mojo 1.2.0 capability probes

Toolchain: Mojo `1.2.0 (2016d0cd)` via `.venv/bin/mojo`. All probes live in
`../experiments/` with captured stdout. Every claim below names the probe
that demonstrates it.

## Strings and code points (`mojo_dp_probe.mojo`)

- `len(s)` is **rejected** for strings; the compiler demands an explicit
  unit: `s.byte_length()`, `len(s.codepoints())`, or `len(s.graphemes())`.
- `s.codepoints()` yields `Codepoint` values; `Int(cp)` gives the scalar
  value; `Codepoint(97)` constructs one. `ord("é") == 233`.
- `CodepointsIter` is **not subscriptable** — `cps[0]` does not compile.
  Materialize with `for cp in s.codepoints(): out.append(Int(cp))` into
  `List[Int]`; cost is ~3.6 µs for 2048 code points (negligible next to
  any DP).
- `s[codepoint=a:b]` slices by code points; `s[byte=a:b]` by bytes; bare
  `s[a:b]` does not compile. `s.graphemes()` exists but counts user
  clusters (family emoji: 7 code points, 1 grapheme) — wrong unit here.
- NUL (`"\x00"`) is a valid code point; empty string yields zero code
  points. Invalid UTF-8 (surrogates, overlongs, truncated sequences)
  raises on `String(from_utf8=...)` — verified in `/tmp` scratch probes
  (surrogate `ED A0 80`, overlong `C0 80`, truncated `E2` all raise
  `Cannot construct a String from invalid UTF-8 data`).

## Arithmetic hazards (scratch probes, findings recorded here)

- **Overflow wraps silently**: `UInt8(255) + 1 == 0`,
  `Int.MAX + 1 == Int.MIN`, no trap, no error. Distance accumulators
  must use a wide type (`Int`) with explicit length guards; never rely on
  a trap that does not exist.
- **Shifts at the bit width are target-dependent**: `UInt128(1) <<
  UInt128(128)` constant-folds to `0`, but the same shift with a runtime
  amount yields `1` (count masked). `UInt64(1) << UInt64(64)` folds to
  `0`. Consequence: bit-parallel code must branch on `n == 64` /
  `n == 128` (`vp = MAX`) instead of shifting by the width. The
  128-bit probe initially failed exactly one case (n=128, Myers 231 vs
  true 113) for this reason; after the guard all n=0..128 pass.

## Algorithms (`mojo_dp_probe.mojo`, `mojo_myers_probe.mojo`, `mojo_myers128_probe.mojo`)

- Two-row O(n·m) DP for unit-cost distance and LCS-based ratio matches
  all 9 reference values (kitten/sitting, lewenstein/levenshtein, astral,
  NFD, empty). `min(a, b, c)` / `max(a, b)` with three/two args work;
  `List[Int]` swap via `var swap = prev^` works.
- Myers bit-parallel (64-bit, ASCII, n ≤ 64): matches DP on 9 fixed cases
  plus 200 randomized pairs; ~611 ns at n=64 vs ~25 µs DP (~40x).
- Myers bit-parallel (128-bit, ASCII, n ≤ 128): matches DP on every
  n=0..128 random pair; ~1.2 µs at n=128 vs ~98 µs DP (~80x).
- Arbitrary lengths need a blocked bit-vector (`List[UInt64]` words with
  carry propagation). Not probed — named as the Phase 1 spike, with the
  shift-guard rule above as a known requirement.
- `UInt128` exists; `BigInt` does not (`use of unknown declaration`).
  Bit ops (`&`, `|`, `^`, `~`, `<<`, `>>`) on `UInt64` behave as expected
  below the width.

## Errors and test harness (`mojo_testsuite_probe.mojo`)

- `raise Error("...")` from a `raises` function, `with assert_raises(contains=...)`,
  and `TestSuite.discover_tests[__functions_in_module()]().run()` all work
  (2/2 pass). The validation-error pattern for v0.1 (bad weights, bad
  cutoffs, non-`str` input at the CLI boundary) is therefore available.
- `from std.testing import TestSuite, assert_equal, assert_raises` and
  `from std.time import perf_counter_ns` match the msgpack precedent.

## What was NOT probed (explicit gaps)

- `Dict` performance for the Peq table over the full code-point range
  (probes use a 128-entry `List` for ASCII); the Unicode Peq strategy is
  a Phase 1 design decision.
- CLI framing/transport — msgpack's `protocol.mojo` already proves the
  pattern; Levenshtein reuses it in Phase 1 without new capability risk.
