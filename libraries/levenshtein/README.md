# Levenshtein (Mojo port)

## Status: v0.1.0 release candidate — implemented, optimized, and audited

Phase reports: [`PHASE0_RESULTS.md`](PHASE0_RESULTS.md) (reference
audit) · [`PHASE1_RESULTS.md`](PHASE1_RESULTS.md) (core
implementation) · [`PHASE2_RESULTS.md`](PHASE2_RESULTS.md)
(benchmarks) · [`PHASE3_RESULTS.md`](PHASE3_RESULTS.md)
(optimizations). Curated release summary:
[`docs/benchmarks/releases/levenshtein-v0.1.md`](../../docs/benchmarks/releases/levenshtein-v0.1.md).
Reference audit: [`docs/reference-audit.md`](docs/reference-audit.md) ·
Reference audit: [`docs/reference-audit.md`](docs/reference-audit.md) ·
Unicode: [`docs/unicode-semantics.md`](docs/unicode-semantics.md) ·
Mojo probes: [`docs/mojo-probes.md`](docs/mojo-probes.md) ·
benchmarks: [`docs/benchmark-design.md`](docs/benchmark-design.md) ·
raw probe outputs: [`experiments/`](experiments/).

## Library description

Edit distance and string similarity: Levenshtein distance, Indel-based
ratio similarity, and Hamming distance, used in fuzzy matching, spell
correction, and record linkage.

## Reference and license

- Behavior oracle: `rapidfuzz==3.14.6` (**MIT**) — covers every probed
  behavior of the `Levenshtein==0.27.5` wrapper (GPL-2.0-or-later),
  which is therefore **not** a dependency. The GPL package was used for
  black-box observation only and must not enter dependency files or
  committed code, per [THIRD_PARTY_NOTICES.md](../../THIRD_PARTY_NOTICES.md).
- Pinned in `python_reference/requirements.txt` and the dev
  dependency-group; the generator refuses to run against any other
  rapidfuzz version.
- Upstream source is not vendored.

## v0.1 scope (implemented)

`distance` (unit + positive-integer weights, integer `score_cutoff`),
`ratio` (Indel normalized similarity), `hamming` — Unicode `str` input
only, code-point semantics, no normalization. Deferred with reasons in
`PHASE0_RESULTS.md` §2: `normalized_*` (not in the reference package),
Jaro/Jaro-Winkler, the editops/opcodes/matching-blocks family, the
median family, `StringMatcher`, `processor`/`score_hint`/similarity
cutoffs.

## Implementation

- `mojo/mojo_levenshtein/` — `unicode`, `distance`, `ratio`,
  `hamming`, `protocol` (framing copied from the MessagePack CLI
  pattern, decoupled from it), `algorithms/` (two-row DP oracle,
  blocked Myers bit-parallel, blocked bit-parallel LCS over `UInt64`
  words).
- `mojo/cli.mojo` — batch CLI: `PING 0x01`, `ECHO 0x02`,
  `DISTANCE 0x20`, `RATIO 0x21`, `HAMMING 0x22`; responses carry a
  status byte; malformed input yields error frames, never crashes.
  u64 weights beyond `Int` range are rejected; an above-range cutoff
  is exactly equivalent to no truncation and treated as such.
- Unit weights dispatch to blocked Myers (shorter input as pattern);
  weighted costs use the DP oracle; both paths agree exactly.
- Common affix trimming precedes both cores (exact for positive
  costs; validated on untrimmed inputs so guards keep their meaning).
- `ratio` uses blocked bit-parallel LCS (shorter input as pattern)
  with affix trimming and a no-copy fast path — still bit-exact vs
  the oracle; `levenshtein_ratio` is marked `raises` like
  `myers_distance` (all callers already in `raises` contexts).
- `hamming` compares code points in a single lockstep pass with no
  materialized arrays.
- Integer overflow and full-width shifts are guarded by construction
  (see `PHASE1_RESULTS.md` §4 and `tests/mojo/test_guards.mojo`).

## Compatibility objectives (all met)

- Exact oracle values for all in-scope inputs, weights, and integer
  cutoffs: 434/434 goldens natively, 432/434 through the CLI (the 2
  skips are u64-inencodable negatives, covered natively).
- Code-point unit for all lengths; lone surrogates and non-UTF-8 bytes
  are rejected with validation errors.
- Golden vectors with a drift gate; assumption tests pinning oracle
  edge behavior.

## Testing

- Native: 8 suites, 40 tests (`test_distance`, `test_ratio`,
  `test_hamming`, `test_myers_parity` with 450 DP-vs-Myers pairs,
  `test_lcs_parity` with 450 DP-vs-bit-parallel pairs,
  `test_trimming` with 10 affix/weighted/cutoff cases,
  `test_guards`, `test_generated_vectors`).
- Python: 24 tests (`test_cli`, `test_golden_vectors`,
  `test_oracle_assumptions`, `test_randomized_properties` with 205
  fresh pairs).
- Repo-wide `run_all_tests.py` exits 0: 153 pytest + 13 native suites
  (79 msgpack + 40 levenshtein tests), both drift gates current.

## Benchmarking (Phase 2 complete; Phase 3 optimizations applied)

41 deterministic workloads (short/medium/long/xlong/huge ASCII, unequal
lengths both orders, repeated-character stress, accents, CJK, astral
emoji, combining sequences, empty edge cases, 1–2048 Myers boundary
sweep), seven paths (naive Python DP, RapidFuzz `_py` fallback,
RapidFuzz C++, native production, internal Mojo DP/Myers), in-process
timing, cold-compile and RSS reported separately. Phase 3 results
(new / Phase 2 baseline): distance with affix trimming is 22–28x
faster on identical 2048-char inputs and unchanged elsewhere;
bit-parallel LCS makes ratio 4–45x faster (identical 2048-char inputs
collapse ~1000x with trimming); materialization-free hamming is
2–5x faster on every workload. Full tables and analysis:
[`PHASE2_RESULTS.md`](PHASE2_RESULTS.md) (baseline),
[`PHASE3_RESULTS.md`](PHASE3_RESULTS.md) (optimizations); curated
summary:
[`docs/benchmarks/releases/levenshtein-v0.1.md`](../../docs/benchmarks/releases/levenshtein-v0.1.md).
Reproduce with
`.venv/bin/python libraries/levenshtein/benchmarks/run_benchmarks.py`.

## Current status

Phase 4 complete — full scope, safety, and compatibility audit passed;
benchmarks verified on the final tree; release summary published.
Awaiting review and release decision; no other library port starts
until this report is reviewed.
