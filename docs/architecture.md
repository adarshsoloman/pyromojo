# Architecture

## Repository layout

PyroMojo is a monorepo of independent library ports plus shared engineering
infrastructure.

```
libraries/<library>/
├── mojo/                  Native Mojo sources and Mojo-side tests entry points
├── python_reference/      Reference driver scripts and pinned requirements
├── tests/
│   ├── mojo/              Native Mojo unit tests
│   ├── python_compat/     Python tests comparing Mojo output to the reference
│   └── vectors/           Library-specific golden test vectors
├── benchmarks/            Library benchmark definitions and runners
├── examples/              Minimal usage examples
└── README.md              Scope, compatibility, and status

shared/
├── benchmark_utils/       Timing harness, statistics, environment capture
├── test_vectors/
│   ├── schema/            Versioned JSON schema for vector files
│   └── generators/        Deterministic vector generation tools
├── validation/            Shared validators for outputs and vector integrity
└── reporting/             Report rendering for tests and benchmarks

scripts/                   Repository-level orchestration
benchmarks/configs/        Shared benchmark configuration files
docs/                      Architecture, roadmap, benchmark methodology
```

## Library isolation

- A library may depend on `shared/` but **must not** import another library.
- Each library owns its tests, vectors, benchmarks, and documentation.
- Adding or changing a library must not require editing another library's code.
- Shared code is limited to infrastructure that has at least two real consumers.
  Speculative abstraction is not added to `shared/`.

This keeps ports independently reviewable and prevents a single failing port
from blocking unrelated work.

## Shared infrastructure responsibilities

### Test vectors

Golden vectors are the contract between the reference implementation and the
Mojo implementation. They are:

- Stored as versioned, human-inspectable files.
- Generated deterministically from a recorded seed and generator version.
- Validated against a schema before use.
- Committed once stable, so compatibility does not silently drift.

### Validation

Validation covers output equality, error behaviour, and vector file integrity.
It reports precise diffs so a failure identifies the exact input and field.

### Benchmark utilities

Benchmark utilities provide:

- A common timing harness and warm-up policy.
- Environment capture (CPU, OS, Python, Mojo toolchain, compiler flags).
- Cold-compilation versus warm-execution separation.
- Machine-readable output for report generation.

### Reporting

Reporting renders test and benchmark results into Markdown or JSON artifacts.
Generated reports are excluded from version control by default; curated release
reports may be committed deliberately under `docs/benchmarks/`.

## Native Mojo implementation principles

- **Match observable behaviour first.** Public output, error semantics, and edge
  cases follow the reference. Optimisation comes after correctness.
- **Use the installed toolchain's syntax.** No unverified APIs or configuration
  are assumed; implementations target the Mojo toolchain verified locally and
  recorded in benchmark metadata.
- **Prefer explicit memory and ownership discipline.** Avoid hidden allocation in
  hot paths; document allocation behaviour where it matters.
- **No FFI shortcut for the core port.** A port may use Python interop for
  testing and comparison, but the measured native path must be implemented in
  Mojo.
- **Document deviations.** Any intentional difference from the reference is
  listed in the library README with its rationale.
- **Keep the surface small.** Implement the documented subset first; expand only
  when vectors and tests cover the new behaviour.
