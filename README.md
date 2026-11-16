<div align="center">

# 🔥 PyroMojo

**Native Mojo ports of widely used Python libraries.**<br>
Verified against the originals. Benchmarked honestly.

<br>

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg?style=flat-square)](LICENSE)
[![Mojo](https://img.shields.io/badge/Mojo-1.2.0-ff5a1f.svg?style=flat-square)](https://www.modular.com/mojo)
[![Python](https://img.shields.io/badge/Python-%E2%89%A53.11-3776ab.svg?style=flat-square)](https://www.python.org)
[![Tests](https://img.shields.io/github/actions/workflow/status/adarshsoloman/pyromojo/tests.yml?style=flat-square&label=tests)](https://github.com/adarshsoloman/pyromojo/actions/workflows/tests.yml)
[![Sponsor](https://img.shields.io/badge/Sponsor-%E2%99%A5-ea4aaa.svg?style=flat-square)](https://github.com/sponsors/adarshsoloman)

<sub>4 libraries shipped &nbsp;·&nbsp; 1,800+ golden vectors &nbsp;·&nbsp; every number below is measured, not claimed</sub>

</div>

<br>

## Sponsors

PyroMojo is built and benchmarked by one maintainer. Sponsors fund compute for benchmarking and CI, AI tooling credits, and time for the profiling and optimization work. **Five slots are open.**

<div align="center">
<table>
  <tr>
    <td align="center" width="20%"><br><a href="https://github.com/sponsors/adarshsoloman"><b>Your logo</b></a><br><sub>Slot 1</sub><br><br></td>
    <td align="center" width="20%"><br><a href="https://github.com/sponsors/adarshsoloman"><b>Your logo</b></a><br><sub>Slot 2</sub><br><br></td>
    <td align="center" width="20%"><br><a href="https://github.com/sponsors/adarshsoloman"><b>Your logo</b></a><br><sub>Slot 3</sub><br><br></td>
    <td align="center" width="20%"><br><a href="https://github.com/sponsors/adarshsoloman"><b>Your logo</b></a><br><sub>Slot 4</sub><br><br></td>
    <td align="center" width="20%"><br><a href="https://github.com/sponsors/adarshsoloman"><b>Your logo</b></a><br><sub>Slot 5</sub><br><br></td>
  </tr>
</table>

<sub>Funding · AI credits · cloud compute &nbsp;→&nbsp; <a href="https://github.com/sponsors/adarshsoloman">github.com/sponsors/adarshsoloman</a></sub>
</div>

<br>

## Why PyroMojo

For every library, PyroMojo answers three questions:

1. Can its public behaviour be reproduced natively in Mojo?
2. Can that be verified rigorously against the Python reference?
3. What is the measured performance, stated honestly?

A Mojo port is **not assumed to be faster**. Results are published with reproducible evidence, including the cases where the reference wins.

<br>

## Libraries

| | Library | Version | What it is | Verification |
|:-:|---|:-:|---|---|
| 01 | [MessagePack](libraries/msgpack/) | `v0.1.0` | Binary serialization codec | 162 vectors · 79 native + 129 Python tests |
| 02 | [Levenshtein](libraries/levenshtein/) | `v0.1.0` | String distance and similarity | 434 vectors · 40 native + 25 Python tests |
| 03 | [Bitarray](libraries/bitarray/) | `v0.1.0` | Packed-bit arrays | 266 vectors · 74 native + 391 Python tests |
| 04 | [Audioop](libraries/audioop/) | `v0.1.0` | CPython 3.12 `audioop`, 26/26 operations | 1,277 vectors · 105 native + 136 Python tests |
| 05 | [Resampy](libraries/resampy/) | planned | Audio resampling | not started |

<br>

## Honest benchmarks

Three-way comparisons: pure Python, the optimized native reference, and Mojo. Every result passes an exact-equality correctness gate before it counts.

| Library | vs pure Python | vs optimized C / C++ |
|---|---|---|
| Audioop | ~40× faster | ~0.26× (C typically 2–20× faster; `getsample` ~2.7× faster in Mojo) |
| Bitarray | ~2–205× faster | matches or beats at 64-bit sizes; trails ~2–75× at 1 Mibit |
| Levenshtein | up to ~45× faster than the untrimmed baseline (ratio) | slower, ~2–9× on distance |
| MessagePack | n/a | up to ~4× faster on small-map encode; binary encode 7.4× slower |

Neither side is universally faster. The gaps have identified causes (allocation, byte-serial loops, scalar arithmetic) and are the subject of the next phase: **profile first, then optimize.**

<sub>Full tables and methodology: [Audioop](libraries/audioop/benchmarks/reports/BENCHMARK_REPORT.md) · [Bitarray](libraries/bitarray/benchmarks/README.md) · [Levenshtein](docs/benchmarks/releases/levenshtein-v0.1.md) · [MessagePack](docs/benchmarks/releases/msgpack-v0.1.md)</sub>

<br>

## Method

Every port follows the same pipeline, so a result in one library means the same thing in the next.

```
reference audit → toolchain probes → native port → golden vectors
      → native + Python compatibility tests → benchmarks → tagged release
```

- **Pinned references.** `msgpack==1.2.4` · `rapidfuzz==3.14.6` · `bitarray==3.12.3` · CPython 3.12.3. Upstream source is never vendored.
- **Golden vectors.** Deterministic, schema-validated, drift-checked on every run.
- **Cross-language tests.** Error behaviour is compared too: bad input must fail predictably.
- **Documented deviations.** Every intentional difference from the reference is listed with its rationale.
- **Reproducible benchmarks.** Warmup, repeated samples, environment metadata captured, cold compile reported separately.

<details>
<summary><b>Reference licenses and attribution</b></summary>

<br>

| Port | Pinned reference | Reference license |
|---|---|---|
| MessagePack | `msgpack` | Apache-2.0 |
| Levenshtein | [`rapidfuzz`](https://github.com/rapidfuzz/RapidFuzz) | MIT |
| Bitarray | [`bitarray`](https://github.com/ilanschnell/bitarray) | PSF-2.0 |
| Audioop | CPython 3.12 `audioop` | PSF-2.0 |

The GPL-licensed `Levenshtein` wrapper package is used only for black-box observation and never enters the code, tests, or dependencies. Third-party notices: [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

</details>

<br>

## Quick start

Requires [uv](https://docs.astral.sh/uv/) and Python 3.11+. Run from the repository root.

```bash
uv sync --extra dev
.venv/bin/pytest -q

# full pipeline: lint, vector drift check, pytest, every native Mojo suite
.venv/bin/python scripts/run_all_tests.py
```

<br>

## Roadmap

| Phase | Goal | Status |
|---|---|---|
| 1 | Repository foundation | ✅ Complete |
| 2 | MessagePack, the first complete port | ✅ Complete |
| 3 | First five verified ports | 🔶 4 of 5 |
| 4 | Expand toward 20 libraries | ⬜ Planned |
| 5 | Performance analysis and upstream contributions | ⬜ Planned |

Details and exit criteria: [docs/roadmap.md](docs/roadmap.md).

<br>

<details>
<summary><b>Repository structure</b></summary>

<br>

```text
pyromojo/
├── libraries/
│   ├── msgpack/  levenshtein/  bitarray/  audioop/    # shipped, v0.1.0
│   └── resampy/                                       # planned
│       └── (each) mojo/ · python_reference/ · tests/ · benchmarks/ · docs/
├── shared/
│   ├── benchmark_utils/      # timing harness, statistics, environment capture
│   ├── test_vectors/         # versioned schema + deterministic generators
│   └── validation/           # output and vector-integrity validators
├── scripts/                  # run_all_tests · check_compatibility · run_all_benchmarks
├── docs/                     # architecture · roadmap · benchmark releases
└── CONTRIBUTING.md · LICENSE · THIRD_PARTY_NOTICES.md
```

A library may depend on `shared/`, never on another library. See [docs/architecture.md](docs/architecture.md).

</details>

<details>
<summary><b>Contributing</b></summary>

<br>

- Open or claim an issue first. For a new port, state the target library, the pinned reference version, and the intended compatibility surface.
- Work inside a single library directory. `shared/` changes need a second real consumer.
- Keep `main` green, match the installed Mojo toolchain's syntax, and pass `ruff` (100-character lines).
- A change is complete only when Mojo unit tests, Python compatibility tests, and golden vectors cover it.

Full guide: [CONTRIBUTING.md](CONTRIBUTING.md).

</details>

<br>

<div align="center">

**Apache-2.0** &nbsp;·&nbsp; Built by [Adarsh](https://github.com/adarshsoloman) &nbsp;·&nbsp; [Sponsor this work](https://github.com/sponsors/adarshsoloman)

</div>
