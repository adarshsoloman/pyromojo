# Benchmark Methodology

This document defines how PyroMojo benchmarks are produced and reported. It is
binding for any performance number published under this repository.

## Goals

- Compare implementations honestly under identical workloads.
- Separate compile cost from execution cost.
- Make every published number reproducible from a clean checkout.

No performance claim is published without a benchmark that follows this
methodology.

## Three-way comparison strategy

Each library benchmark measures three paths with the same inputs:

1. **Python reference** — the pinned upstream implementation.
2. **Native Mojo** — the port executed directly by the Mojo runtime.
3. **Mojo from Python** — the port invoked through Python interop, so interop
   overhead is visible rather than hidden.

Where a path is not yet available, the report states the gap explicitly instead
of omitting it.

## Reported metrics

- Throughput and per-call latency, with median and dispersion reported.
- Peak memory where the operation is allocation-sensitive.
- Compilation time, recorded separately from execution time.
- Interop overhead (path 3 minus path 2) where applicable.

Single-run numbers are not reportable. Each configuration requires repeated
measurements with a documented warm-up policy.

## Cold compilation versus warm execution

These are distinct measurements and must never be combined:

- **Cold compilation:** build the artifact from source on a clean state and
  record wall-clock compile time and toolchain version.
- **Warm execution:** run the already-built artifact, with warm-up iterations
  excluded from reported statistics.

Reports present both. A faster warm path does not imply a faster developer loop.

Curated, review-ready release summaries live in `releases/` (for example,
`releases/msgpack-v0.1.md`). Raw per-run reports stay git-ignored.

## Reproducibility requirements

Every benchmark report records:

- Git commit of PyroMojo and of the reference dependency (exact pinned version).
- Mojo toolchain version and relevant compiler flags.
- Python version and interpreter build.
- CPU model, core count, memory, and operating system.
- Benchmark configuration file and input vector identifiers or seeds.
- Warm-up and iteration counts, and the aggregation method.

Configuration files live in `benchmarks/configs/` or the library's
`benchmarks/` directory and are version-controlled. Temporary results and
generated reports are ignored by default; curated release reports may be
committed deliberately under `docs/benchmarks/`.

## Fairness rules

- Identical logical inputs and identical validation for all paths.
- No pre-computation unless every path is allowed the same pre-computation.
- Reference code is used as published, without hand-tuning beyond documented
  configuration.
- Failures, timeouts, and unsupported cases are reported, not dropped.
- Difference between measured and published results larger than the stated
  dispersion must be explained or the report withdrawn.

## Reporting template

Reports include: summary, environment, configuration, results tables, analysis,
limitations, and reproduction commands. Any deviation from this methodology is
listed in the report.
