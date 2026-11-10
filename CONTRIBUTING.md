# Contributing to PyroMojo

PyroMojo welcomes contributions that improve correctness, reproducibility, or
maintainability. This project ports libraries to native Mojo and verifies them
against Python; both halves of that work are equally important.

## Development workflow

1. Open or claim an issue describing the change. For a new port, state the
   target library, the pinned reference version, and the intended compatibility
   surface.
2. Work inside a single library directory where possible. Changes to `shared/`
   require a second real consumer.
3. Keep `main` green. Each change must build and test locally before review.
4. Submit a focused pull request: one library or one infrastructure concern.
5. Address review comments and keep the history clean.

Do not commit generated reports, benchmark scratch data, build artifacts, or
pinned environment directories.

## Code quality expectations

- Match the installed Mojo toolchain's current syntax. Do not use unverified
  compiler flags or undocumented APIs.
- Python code must pass `ruff` with the repository configuration and use a
  100-character line limit.
- Prefer small, explicit code over abstraction. Add shared helpers only when
  duplication is demonstrated, not predicted.
- Document allocation-sensitive behaviour and any deliberate compatibility
  deviation.
- Do not add a dependency without stating why and confirming its license.

## Testing requirements

A change is not complete until:

- Mojo unit tests cover the new behaviour, including boundary and invalid-input
  cases.
- Python compatibility tests compare behaviour against the pinned reference.
- Golden vectors exist for any new observable behaviour and are validated
  against the shared schema.
- `pytest` passes locally.
- The test suite fails if the implementation is reverted (no vacuous tests).

Tests must be deterministic. Randomised inputs require a recorded seed.

## Benchmark integrity requirements

- Follow [docs/benchmarks/README.md](docs/benchmarks/README.md).
- Report cold compilation and warm execution separately.
- Include environment metadata and the benchmark configuration in every report.
- Do not publish a speed claim from a single run or an unreproducible setup.
- Report regressions and unsupported cases; do not remove them from results.
- Never tune the reference implementation beyond documented configuration to
  make a comparison favourable.

## Documentation expectations

- Every library README states scope, reference package, compatibility
  objectives, testing requirements, benchmark requirements, and current status.
- Update the library README and roadmap status when behaviour or scope changes.
- New third-party dependencies must be documented per
  [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md); copyleft dependencies
  require an explicit compatibility review before distribution.

## License

By contributing, you agree that your contributions are licensed under the
Apache License 2.0.
