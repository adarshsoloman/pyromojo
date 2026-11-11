# PyroMojo

Native [Mojo](https://www.modular.com/mojo) implementations of widely used Python
libraries, verified against the original Python behaviour and benchmarked with
reproducible, shared test vectors.

> **Status: initial scaffolding.** No library port is implemented yet. This
> repository currently contains only the project structure, policy documents,
> and configuration needed to begin work on Msgpack.

## Motivation

Python's ecosystem is vast, but CPU-bound library code written in C, Cython, or
pure Python often leaves performance on the table and is difficult to extend.
Mojo offers Python-like ergonomics with systems-level control, predictable
performance, and direct interoperability with the Python ecosystem.

PyroMojo exists to answer a concrete engineering question for each library:

1. Can the library's public behaviour be reproduced natively in Mojo?
2. Can that implementation be verified rigorously against the Python reference?
3. What are the measured performance characteristics, stated honestly?

The project does **not** assume that a Mojo port is faster. Performance claims
will only be published alongside reproducible benchmark evidence.

## Long-term objectives

- Port at least 20 Python libraries to native Mojo.
- Keep every port independently usable, testable, and benchmarkable.
- Provide Python reference implementations or pinned reference dependencies for
  every port.
- Maintain shared golden test vectors so all implementations agree on the same
  inputs and outputs.
- Produce reproducible benchmarks with documented methodology.
- Document compatibility boundaries, deviations, and known limitations.

## Architecture overview

```
libraries/<name>/     One self-contained port: Mojo source, Python reference,
                      tests, vectors, benchmarks, examples, README.
shared/               Cross-library infrastructure: benchmark utilities, test
                      vector schema and generators, validation, reporting.
scripts/              Repository-level orchestration for tests, benchmarks,
                      reports, and compatibility checks.
benchmarks/configs/   Shared benchmark configuration files.
docs/                 Architecture, roadmap, and benchmark methodology.
```

Each library is isolated: it may depend on `shared/` infrastructure, but
libraries must not depend on one another. See
[docs/architecture.md](docs/architecture.md) for details.

## Planned library ports

| Library       | Purpose                                   | Status      |
|---------------|-------------------------------------------|-------------|
| `msgpack`     | Binary serialization                      | PHASE 1 FOUNDATIONS |
| `levenshtein` | Edit distance and string similarity       | NOT STARTED |
| `audioop`     | Legacy audio sample manipulation          | NOT STARTED |
| `bitarray`    | Compact bit array operations              | NOT STARTED |
| `resampy`     | Audio resampling                          | NOT STARTED |

The Msgpack port is the reference project for the full workflow and is the
first planned implementation.

## Testing philosophy

Testing is layered, and each layer has a clear job:

- **Mojo unit tests** exercise native implementation behaviour.
- **Python compatibility tests** compare the Mojo implementation against the
  reference Python package through a common interface.
- **Golden vectors** are shared, versioned inputs and expected outputs that both
  implementations must satisfy.
- **Invalid-input tests** are first-class: malformed, truncated, and hostile
  inputs must fail predictably, not silently.

A port is not considered verified until all layers agree.

## Benchmarking philosophy

Benchmarks compare three paths under the same workload:

1. The reference Python implementation.
2. The native Mojo implementation.
3. The Mojo implementation called from Python (interop overhead included).

Cold compilation and warm execution are reported separately. Benchmark inputs,
toolchain versions, hardware, and methodology must be recorded so results can be
reproduced. See [docs/benchmarks/README.md](docs/benchmarks/README.md).

## Contributing

Development workflow, quality expectations, and review requirements are
documented in [CONTRIBUTING.md](CONTRIBUTING.md).

## License

Apache License 2.0. See [LICENSE](LICENSE) and
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) for third-party dependency
policy.
