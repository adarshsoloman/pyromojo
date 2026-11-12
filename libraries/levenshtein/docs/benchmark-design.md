# Benchmark design (Phase 0 feasibility)

Raw outputs: `../experiments/perf_feasibility_output.txt`,
`../experiments/baseline_paths_output.txt`. Single-process,
min-of-repeats nanosecond timings. **Feasibility numbers, not published
results** — no cold-compile control, no machine spec, no repetition
across runs.

## The four paths (all measured on identical inputs)

| path | n=64 dist | n=512 dist | n=2048 dist | notes |
|---|---|---|---|---|
| naive Python two-row DP (local) | 381 µs | 30.6 ms | (too slow to run) | honest floor; O(n·m) |
| `rapidfuzz` pure-Python `_py` | 67.5 µs | 503 µs | 3.7 ms | Myers bit-parallel over big ints; algorithmic parity |
| native Mojo two-row DP (probe) | 26.5 µs | 1.7 ms | 27.6 ms | correctness-first candidate; O(n·m) |
| pinned C++ reference | 0.44 µs | 11.4 µs | 111 µs | ceiling/oracle; bit-parallel + SIMD paths |

Ratio (Indel/LCS) shows the same ordering: at n=512, naive 16.3 ms,
`_py` 142 µs, Mojo DP 0.83 ms, C++ 4.0 µs. Unicode vs ASCII inputs are
indistinguishable in C++ timing (361 ns both), so one Unicode workload
per size suffices.

Two ratios matter. Mojo DP beats naive Python ~14x at n=64 and ~18x at
n=512, but loses to the optimized `_py` fallback above n≈256 (Mojo
27.6 ms vs `_py` 3.7 ms at n=2048) and trails C++ by ~250x there. The
Mojo Myers probes reverse this: 611 ns at n=64 (~1.3x C++) and 1.2 µs
at n=128. Conclusion: **O(n·m) DP is a valid correctness-first Phase 1
baseline but cannot be the performance story; a blocked Myers/LCS
bit-parallel implementation is required to approach the reference, and
its feasibility is demonstrated for the single-word cases.**

## Workload categories (carried into Phase 1)

- `equal` (best case for prefix-skip optimizations), `one-sub`
  (near-miss), `random` (general), `unrelated` (worst case, `a`*n vs
  `b`*n). Sizes 8, 16, 32, 64, 128, 256, 512, 1024, 2048 — the
  crossover where bit-parallel beats DP sits between 64 and 256.
- One Unicode workload per size (mixed scripts, astral, NFD pair) to pin
  code-point semantics; byte-length and code-point-length must both be
  recorded since they diverge.
- Edge cases: empty/empty, empty/nonempty, single code point, lone
  surrogate (reference-only; Mojo must error — see `unicode-semantics`).

## Harness reuse (no new infrastructure in Phase 0)

- In-process timing: `bench.mojo` pattern (`perf_counter_ns` around the
  call, min-of-N, ns/op) — proven by the probes.
- Deterministic workloads: `workloads.py` pattern (seeded RNG, fixed
  sizes); Phase 1 adds a golden-vector generator with a `--check` drift
  gate mirroring `generate_vectors.py`.
- Compatibility assertions: `test_reference_assumptions.py` pattern —
  golden values come from the captured probe outputs, not from memory.
- Cold-compile timing and peak RSS in `run_benchmarks.py` apply
  unchanged (Mojo compile cost dominates short runs; report it).

## Proposed Phase 1 gates (to be ratified, not enforced here)

1. Correctness: 100% agreement with the MIT oracle (`rapidfuzz`) on the
   golden corpus, all weights/cutoffs in the v0.1 subset.
2. Floor: Mojo beats naive Python DP by ≥5x at every size ≤512.
3. Stretch: single-word Myers path lands within 3x of C++ at n ≤ 128;
   blocked bit-vector spike scheduled before any large-n performance
   claim is made.
4. No large-n performance claim without the blocked implementation and
   the cold-compile/RSS reporting the repo standard requires.
