# Phase 1D3 reference probes: `reverse`, `fill`, `copy`, `rotate`, `find`, `index`

Pinned oracle: `bitarray==3.12.3`. Every claim below was observed by
direct black-box probing (see `tests/python_compat/test_sequence_extras_oracle.py`,
which encodes the same expectations as executable tests). Nothing here
is implemented yet at the time of writing.

## 1. `reverse()` — exists, in-place, returns `None`

- Signature `reverse()`, no arguments (positional-only is moot).
- Reverses the LOGICAL bit sequence in place; `"10110011"` becomes
  `"11001101"` in both endiannesses (endianness selects physical layout,
  reversal is logical).
- Empty and single-bit arrays are no-ops returning `None`.
- Endianness flag preserved; padding re-normalized by the operation
  (length unchanged, so pad count is unchanged too).

## 2. `fill(m=8)` — exists, pads to a multiple of `m`, returns count

- Signature `fill(m=8, /)`: positional-only, `m` a positive `int`.
- Appends zeros so the length becomes a multiple of `m`; returns the
  number of bits added (`range(m)`).
- `"10110".fill()` → `"10110000"`, returns 3. Already-aligned lengths
  return 0 and change nothing. Empty array returns 0.
- `m=1` always returns 0; `m=0`/negative → `ValueError: m must be a
  positive integer`; non-int `m` → `TypeError`; keyword `m=` →
  `TypeError` (positional-only).
- Endianness preserved; appended bits are zeros in both modes.

## 3. `copy()` — exists, independent, same endianness

- Signature `copy()`, no arguments; returns a new `bitarray`.
- Deep independent copy: mutating either side leaves the other intact.
- Empty, single-bit, non-aligned, and multi-byte arrays all copy
  exactly, preserving endianness and length.
- No read-only/frozen behavior involved (frozen is a separate type,
  deferred from v0.1).

## 4. `rotate(k=1)` — exists, in-place right rotation, returns `None`

- Signature `rotate(k=1, /)`: positional-only `int`; non-int →
  `TypeError`; keyword → `TypeError`.
- Positive `k` rotates RIGHT by `k mod n`; negative `k` rotates left
  (equivalently right by `k mod n` with floored modulo).
- `"10110011".rotate(2)` → `"11101100"`; `.rotate(-2)` →
  `"11001110"`; `.rotate(8)`/`.rotate(0)` are identity; large `k`
  reduces modulo length (`10 mod 8 == 2`).
- Empty array: no-op. Single-bit array: identity for any `k`.
- Logical operation: identical results in both endiannesses;
  endianness flag preserved.

## 5. `find(sub, start=0, stop=<end>, right=False)` — exists, `-1` on miss

- All of `sub`, `start`, `stop` positional-only; `right` positional or
  keyword. Returns `int`.
- `sub` may be a bitarray, `0`/`1` (`True`/`False` coerce); anything
  else → `TypeError: sub_bitarray must be bitarray or int, not ...`;
  other ints → `ValueError: bit must be 0 or 1, got ...`.
- Returns the lowest start index with the pattern fully contained in
  the clamped `[start:stop)` window, or the rightmost such index when
  `right=True`; `-1` when absent.
- Matches OVERLAP (`"11"` in `"1111"` → `0`, and the window scan finds
  every overlapping position).
- Empty pattern matches every position `lo..=hi` inclusive (`"101"`
  → `[0,1,2,3]`; with `right=True` → `[3,2,1,0]`); empty window
  (`start >= stop`) matches nothing, even for the empty pattern.
- Bounds clamp like slices (negatives, out-of-range); empty target
  with non-empty pattern → `-1`; empty/empty → `0`.
- Comparison is logical: cross-endian patterns match; endianness of
  either side is irrelevant to the result.

## 6. `index(sub, start=0, stop=<end>, right=False)` — exists, raises on miss

- Identical search semantics to `find` (same arguments, same order,
  same `right` flag), except a miss raises
  `ValueError: bitarray('<bits>') not in bitarray` for sub-bitarray
  patterns and `ValueError: <int> not in bitarray` for int patterns
  (e.g. `0 not in bitarray`).
- `index` of an empty pattern returns `lo` (same as `find`).

## 7. Scope reconciliation outcome

No correction to the frozen v0.1 scope was required: `docs/api-scope.md`
already lists `reverse`, `fill()`, `rotate(k)`, `copy()`, `find`, and
`index` with exactly the semantics probed above (in-place reversal,
zero-pad-to-boundary with pad count, right rotation by `k mod n`,
independent copies, `find` → `-1` / `index` → `ValueError`). The one
refinement is that `fill` accepts an optional multiple `m` (default 8),
which the scope text described only for the default; the Mojo port
implements the full `fill([m])` form.

Out of scope for Phase 1D3 (remain approved-but-unimplemented from
Category A): `pop`/`remove`/`clear`/`setall` and `del a[i]`/`del a[i:j]`
(the Mojo port exposes single-index deletion as `delete(i)` since Mojo
has no `del a[i]` syntax), `append`/`extend`/`insert` already done in
Phase 1C. `sort`, file I/O, buffer protocol, `pack`/`unpack`,
`frozenbitarray`, and everything in Category B/C are unchanged.
