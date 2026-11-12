# Levenshtein — Phase 0 results

Status: investigation complete, no production code written. All claims
below are either directly observed (with the probe file named) or marked
**recommendation**. Nothing here claims an unrun experiment passed.

Probes: `experiments/probe_reference.py` →
`experiments/reference_probe_output.txt`;
`experiments/probe_edge_cases.py` → `experiments/edge_cases_output.txt`;
`experiments/probe_perf_feasibility.py` →
`experiments/perf_feasibility_output.txt`;
`experiments/probe_baseline_paths.py` →
`experiments/baseline_paths_output.txt`;
`experiments/mojo_dp_probe.mojo`, `mojo_myers_probe.mojo`,
`experiments/mojo_myers128_probe.mojo`, `mojo_testsuite_probe.mojo`
(with matching `*_output.txt`). Docs: `docs/reference-audit.md`,
`docs/unicode-semantics.md`, `docs/mojo-probes.md`,
`docs/benchmark-design.md`.

## 1. Reference audit

Pinned: `Levenshtein==0.27.5` (import name `Levenshtein`, Python ≥3.11,
`License-Expression: GPL-2.0-or-later`) with dependency
`rapidfuzz==3.14.6` (`License-Expression: MIT`), installed ephemerally
into `.venv` for black-box observation only. `pyproject.toml` and
`requirements` are untouched.

`Levenshtein` is a thin wrapper: `distance`, `ratio`, `hamming`, `jaro`,
`jaro_winkler`, `editops`, `opcodes`, `matching_blocks`, `apply_edit`,
`subtract_edit`, `inverse` all delegate to `rapidfuzz.distance` and agree
with it on a 403-pair deterministic corpus (unit and integer-weighted
distance, ratio, hamming-pad, Jaro, Jaro-Winkler, Unicode, empties).
Only `median`, `median_improve`, `quickmedian`, `setmedian`, `seqratio`,
`setratio` come from `levenshtein_cpp`. Full delegation table and
signatures: `docs/reference-audit.md` §1–2.

**License decision (recorded): use `rapidfuzz` (MIT) as the
compatibility oracle and benchmark reference; do not depend on the
`Levenshtein` package (GPL-2.0-or-later).** No GPL code is distributed,
linked, or incorporated, per `THIRD_PARTY_NOTICES.md`. This answers the
oracle question: the MIT oracle covers every probed behavior, so the GPL
wrapper buys nothing and costs a copyleft review.

## 2. API scope (v0.1 recommendation)

Include:

- `distance(s1, s2, weights=(1,1,1))` — unit and positive-integer
  weighted costs; rejects zero/negative/float weights and
  non-`(ins, del, sub)` shapes.
- `distance(..., score_cutoff=int)` — exact integer truncation
  `min(distance, cutoff + 1)`; rejects negatives and non-ints.
- `ratio(s1, s2)` — Indel normalized similarity
  `1 - (len1 + len2 - 2·LCS) / (len1 + len2)`; empty/empty → 1.0.
- `hamming(s1, s2, pad=True)` — substitution count plus length
  difference when padding; `ValueError` on unequal lengths with
  `pad=False`.
- Input domain for all four: Unicode `str` only.

Exclude from v0.1 (each with a recorded reason):

- `normalized_distance` / `normalized_similarity` — **they do not exist**
  on the reference package (probed `AttributeError`); they are
  rapidfuzz-class APIs only. `ratio` already is the Indel normalized
  similarity.
- `jaro`, `jaro_winkler` — different algorithm; `prefix_weight` is
  validated against 0.0–1.0 despite 0.0–0.25 documentation (probed).
  Defer until the range bug is dispositioned.
- `editops`, `opcodes`, `matching_blocks`, `apply_edit`,
  `subtract_edit`, `inverse` — tie-breaking is implementation-specific
  (`ab→ba` = insert+delete), `MatchingBlock` is a non-tuple C++ type
  with a sentinel, and bad inputs are silently accepted. Byte parity
  needs the exact C++ reconstruction order: Phase 2+.
- `median*`, `seqratio`, `setratio` — generalized-median heuristics, a
  different problem from pairwise distance.
- `StringMatcher` — not exported (`__all__` omits it), warns its own
  options are unimplemented.
- `processor`, `score_hint`, float `weights`, similarity `score_cutoff`
  — the C++ `ratio` cutoff uses float32 conversion and disagrees with
  exact comparison at boundaries (probed: fails at `0.66666666`, passes
  at `0.6666666`), so cutoffs are untestable as exact API. Revisit in
  Phase 2 as best-effort hints.

## 3. Interop surface

No Python extension and no MessagePack changes in Phase 0 — the v0.1
interop surface is a **framed Mojo CLI reusing the msgpack protocol
pattern** (`uint32_be length | uint8 opcode | payload`, response
`uint8 status | payload`), with new opcodes for
distance/ratio/hamming. Rationale: it reuses proven transport and
validation code, keeps Python↔Mojo comparisons in-process-exact on both
sides of the frame, and needs no dependency or interface changes.
Fuzzing and property-based comparison (random Unicode pairs, weights,
cutoffs against the MIT oracle) run through this CLI plus golden
vectors; the corpus seeds from the Phase 0 probes. A native Python
binding is explicitly out of scope until the algorithm surface is
pinned.

## 4. Performance strategy

The three-way model from the brief is confirmed feasible but redefined
by what the fallback actually is: (1) **naive Python two-row DP**
(local, honest floor), (2) **rapidfuzz `_py` pure-Python**
(bit-parallel, algorithmic parity with the reference), (3) **native
Mojo**. The pinned C++ reference is the ceiling/oracle, reported as a
ratio rather than a competitor. Measured ordering holds across all
workload categories (equal, one-sub, random, unrelated; details in
`docs/benchmark-design.md`).

Historical account of the investigation: the naive-DP-first assumption
failed on contact with measurement — Mojo O(n·m) DP beats naive Python
~14–18x but loses to optimized `_py` above n≈256 and trails C++ ~250x
at n=2048. That forced the bit-parallel spike, which succeeded: Mojo
Myers-64 runs n=64 in ~611 ns (~1.3x C++) and Myers-128 runs n=128 in
~1.2 µs, both verified against DP over hundreds of pairs. The strategy
is therefore **correctness-first DP in Phase 1a, blocked bit-vector
Myers/LCS in Phase 1b before any large-n performance claim**, with
gates defined in `docs/benchmark-design.md` (≥5x over naive Python at
n≤512; within 3x of C++ at n≤128).

## 5. Unicode handling

Unit of comparison is the **Unicode code point** — `ratio("é","e") ==
0.0`, ZWJ family counts 7, `straße→strasse` costs 2 (`docs/unicode-semantics.md`).
No normalization is applied (NFC ≠ NFD, distance 2). The Mojo port
materializes `s.codepoints()` to `List[Int]`; `graphemes()` and byte
views are the wrong unit. Two documented deviations: lone surrogates
are unrepresentable in Mojo `String` (reference: `distance("\ud800","")
== 1`) and non-UTF-8 `bytes` are rejected (reference coerces
per-element in unspecified ways — `distance("abc",[97,98,99]) == 0` but
`distance("é",b"\xc3\xa9") == 2`). v0.1 is `str`-in/`str`-only with
validation errors, never silent coercion.

## 6. Correctness strategy

Golden values come from captured probe outputs, never from memory:
the DP probe asserts 9 reference pairs (including astral, NFD, empty);
the corpus check asserts C++ == `_py` on 403 pairs plus weighted
subsets; Myers-64/128 assert equality with DP on fixed + randomized
pairs (200 pairs, plus every n=0..128). Phase 1 carries this forward as
(1) a deterministic golden-vector file with a `--check` drift gate
(msgpack `generate_vectors.py` pattern), (2) `test_reference_assumptions.py`
pinning oracle behaviors (cutoff truncation, weight validation,
sentinel blocks), and (3) property tests through the CLI (symmetry,
triangle inequality on samples, `apply_edit(editops) == s2` once
editops lands). Fuzzing starts at the CLI boundary in Phase 1b, after
the DP baseline passes goldens.

## 7. Mojo 1.2.0 capabilities (verified)

Strings: explicit-unit iteration (`codepoints()` ✓, `graphemes()` ✓,
`as_bytes()` ✓), `s[codepoint=a:b]` slicing, `Int(cp)`/`Codepoint`
conversion, `ord()` — all working (`mojo_dp_probe.mojo`). Errors and
`TestSuite.discover_tests` pass 2/2 (`mojo_testsuite_probe.mojo`).
`perf_counter_ns`, `List`, `min`/`max` confirmed. Two hazards with
rules: (a) **integer overflow wraps silently** (`UInt8(255)+1 == 0`,
`Int.MAX+1 == Int.MIN`) — use `Int` accumulators with length guards;
(b) **shifts by the full bit width are target-dependent** (literal folds
to 0, runtime masks) — guard `n == 64/128` with `vp = MAX`
(`mojo_myers128_probe.mojo` initially failed exactly n=128 for this
reason). `UInt128` exists; `BigInt` does not. Blocked multi-word Myers
is not yet probed — it is the first Phase 1 spike.

## 8. Benchmark design

Four paths, four workload categories (equal/one-sub/random/unrelated),
sizes 8–2048, ASCII + Unicode, edges (empty, singleton, surrogate on
the reference side only). Harness reuses msgpack's `bench.mojo`
(min-of-N `perf_counter_ns`), seeded `workloads.py`, and
`run_benchmarks.py` cold-compile/RSS/JSON reporting. Numbers in
`docs/benchmark-design.md` are feasibility-grade (single process, no
machine spec) and must not be quoted as results. Phase 1 gates are
proposed there; no gate is enforced by this document.

## 9. Project conventions (applicable, unchanged)

Framed CLI protocol, `MAX_FRAME_BYTES = 64 MiB` discipline, opcode and
status-byte conventions, deterministic generators with drift gates,
typed golden vectors, in-process `bench.mojo`, `test_reference_assumptions.py`,
ruff line-length 100 (`E,F,I,UP,B,SIM`, double quotes), pytest over
`libraries/` (probe scripts are named `probe_*`, never `test_*`, so the
suite stays green), `.venv` Mojo 1.2.0 only. `scripts/run_all_tests.py`
and `check_compatibility.py` hardcode msgpack and must become
library-aware in Phase 1 (flagged, not changed — out of Phase 0 scope).

## 10. Risk register

1. **GPL oracle temptation** — mitigated: MIT `rapidfuzz` covers all
   probed behavior; the GPL package stays out of dependencies and
   committed code.
2. **Cutoff-boundary parity** — C++ float32 conversion vs exact
   comparison; mitigated by deferring similarity cutoffs.
3. **Editops tie-breaking** — silent acceptance of bad inputs and
   C++-specific ordering; mitigated by deferring the whole family.
4. **Shift/overflow UB in bit-parallel code** — mitigated by the guard
   rules in §7, to be encoded as regression tests in Phase 1.
5. **Performance-claim overreach** — DP is ~250x off C++ at n=2048;
   mitigated by the two-stage strategy and the ban on large-n claims
   before the blocked implementation lands.
6. **Scope creep into Jaro/median/StringMatcher** — mitigated by §2's
   explicit exclusion list with reasons.
7. **Surrogate/bytes input gap** — accepted as documented deviations,
   surfaced as errors.

## 11. Phase 1 scope (proposed, not started)

1a. `distance` (unit + positive-int weights, int cutoff) and `ratio`
over `str`, two-row DP, framed CLI, golden vectors + drift gate,
python_compat assumption tests, library-aware test scripts.
1b. Blocked Myers/LCS spike → `hamming`, then performance gates.
Explicitly not in Phase 1: Jaro/Jaro-Winkler, editops family, median
family, StringMatcher, Python bindings, MessagePack modifications.

## 12. Next actions

1. Ratify §2 scope and §11 staging (or amend with reasons).
2. Ratify the MIT-oracle decision in §1/§10 for the record.
3. Open Phase 1a on `distance`+`ratio` DP with golden vectors seeded
   from `experiments/*_output.txt`.
4. Schedule the blocked bit-vector spike as the first 1b task, with
   the §7 guard rules as acceptance tests.
5. Make `scripts/run_all_tests.py` / `check_compatibility.py`
   library-aware when the first Levenshtein tests land.
