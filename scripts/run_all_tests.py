"""Run every repository test suite with the pinned toolchain.

From the repository root::

    uv sync --extra dev
    .venv/bin/python scripts/run_all_tests.py

Steps, in order: ruff lint, ruff format check, golden-vector drift checks,
the full pytest suite, then each native Mojo test executable (built once
into ``build/`` and run). The Resampy native suite and vector drift check
are included. The first failing step stops the run with exit 1 and prints
the failing command plus its output tail; nothing is skipped silently. The
Mojo compiler must report version 1.2.x; anything else fails instead of
falling back to a system toolchain.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUILD_DIR = ROOT / "build"
RESAMPY_TMP = Path("/tmp/pyromojo_resampy_phase3")
# Native test suites. Each suite builds its tests only against its own
# trees; MessagePack entries come first and are untouched by later ones.
MOJO_SUITES = [
    {
        "tests_dir": "libraries/msgpack/tests/mojo",
        "includes": [
            "libraries/msgpack/mojo",
            "libraries/msgpack/tests/mojo",
        ],
        "prefix": "",
        "tests": [
            "test_depth",
            "test_integer_codec",
            "test_scalar_codec",
            "test_container_codec",
            "test_extension_codec",
            "test_regressions",
            "test_generated_vectors",
        ],
    },
    {
        "tests_dir": "libraries/levenshtein/tests/mojo",
        "includes": [
            "libraries/levenshtein/mojo",
            "libraries/levenshtein/tests/mojo",
        ],
        "prefix": "levenshtein_",
        "tests": [
            "test_distance",
            "test_ratio",
            "test_hamming",
            "test_myers_parity",
            "test_lcs_parity",
            "test_trimming",
            "test_guards",
            "test_generated_vectors",
        ],
    },
    {
        "tests_dir": "libraries/bitarray/tests/mojo",
        "includes": [
            "libraries/bitarray/mojo",
            "libraries/bitarray/tests/mojo",
        ],
        "prefix": "bitarray_",
        "tests": [
            "test_storage",
            "test_sequence",
            "test_mutation",
            "test_bitwise",
            "test_count_search",
            "test_sequence_extras",
            "test_serialization",
        ],
    },
    {
        "tests_dir": "libraries/audioop/tests/mojo",
        "includes": [
            "libraries/audioop/mojo",
            "libraries/audioop/tests/mojo",
        ],
        "prefix": "audioop_",
        "tests": [
            "test_samples",
            "test_arithmetic",
            "test_statistics",
            "test_peak_analysis",
            "test_channels",
            "test_ratecv",
            "test_g711",
            "test_adpcm",
        ],
    },
    {
        "tests_dir": "libraries/resampy/tests/mojo",
        "includes": [
            "libraries/resampy/mojo",
            "libraries/resampy/tests/mojo",
        ],
        "prefix": "resampy_",
        "build_flags": ["--fp-mode", "contract=off"],
        "tests": [
            "test_signal",
            "test_output",
            "test_float_codec",
            "test_json_codec",
            "test_coefficients",
            "test_numerical_compare",
            "test_golden_vector",
            "test_cli",
            "test_resample",
        ],
    },
]


def _resolve_tool(name: str) -> list[str]:
    venv_tool = ROOT / ".venv" / "bin" / name
    if venv_tool.exists():
        return [str(venv_tool)]
    if shutil.which("uv") is not None:
        return ["uv", "run", name]
    sys.exit(f"run_all_tests: cannot find {name} (.venv/bin/{name} or uv)")


def _audioop_reference_python() -> list[str]:
    """The audioop vectors require the pinned CPython 3.12 reference venv."""
    venv_python = ROOT / "libraries/audioop/python_reference/.venv/bin/python"
    if not venv_python.exists():
        sys.exit(
            "run_all_tests: audioop vector drift check needs the isolated "
            f"CPython 3.12 reference venv at {venv_python}"
        )
    return [str(venv_python)]


def _check_mojo(mojo: list[str]) -> None:
    result = subprocess.run([*mojo, "--version"], capture_output=True, text=True, cwd=ROOT)
    version = (result.stdout + result.stderr).strip()
    print(f"mojo toolchain: {' '.join(mojo)} -> {version}")
    if result.returncode != 0 or "Mojo 1.2." not in version:
        sys.exit(
            "run_all_tests: need the pinned Mojo 1.2.x toolchain "
            f"(.venv/bin/mojo or `uv run mojo`), got: {version!r}"
        )


def _run(label: str, command: list[str], env: dict[str, str] | None = None) -> None:
    print(f"--- {label}: {' '.join(command)}")
    result = subprocess.run(command, capture_output=True, text=True, cwd=ROOT, env=env)
    output = (result.stdout + result.stderr).strip()
    if result.returncode != 0:
        print(output[-4000:])
        sys.exit(f"run_all_tests: FAILED: {label} (exit {result.returncode})")
    tail = output[-500:] if output else "(no output)"
    print(tail)


def main() -> int:
    python = _resolve_tool("python")
    mojo = _resolve_tool("mojo")
    ruff = _resolve_tool("ruff")
    pytest = _resolve_tool("pytest")
    _check_mojo(mojo)

    _run("ruff check", [*ruff, "check", "libraries", "shared", "scripts"])
    _run("ruff format check", [*ruff, "format", "--check", "libraries", "shared", "scripts"])
    _run(
        "vector drift check",
        [*python, "libraries/msgpack/python_reference/generate_vectors.py", "--check"],
    )
    _run(
        "levenshtein vector drift check",
        [*python, "libraries/levenshtein/python_reference/generate_vectors.py", "--check"],
    )
    _run(
        "bitarray vector drift check",
        [*python, "libraries/bitarray/python_reference/generate_vectors.py", "--check"],
    )
    _run(
        "audioop vector drift check",
        [
            *_audioop_reference_python(),
            "libraries/audioop/python_reference/generate_audioop_vectors.py",
            "--check",
        ],
    )
    _run(
        "resampy vector drift check",
        [*python, "libraries/resampy/tests/vectors/generate_resample_vectors.py", "--check"],
    )
    _run("pytest", [*pytest, "-q"])

    BUILD_DIR.mkdir(exist_ok=True)
    RESAMPY_TMP.mkdir(parents=True, exist_ok=True)
    resampy_cli = str(BUILD_DIR / "resampy_cli")
    _run(
        "build resampy CLI",
        [
            *mojo,
            "build",
            "libraries/resampy/mojo/cli.mojo",
            "-I",
            "libraries/resampy/mojo",
            "--fp-mode",
            "contract=off",
            "-o",
            resampy_cli,
        ],
    )
    test_env = {**os.environ, "RESAMPY_CLI": resampy_cli}
    for suite in MOJO_SUITES:
        for name in suite["tests"]:
            binary = str(BUILD_DIR / f"{suite['prefix']}{name}")
            source = f"{suite['tests_dir']}/{name}.mojo"
            command = [*mojo, "build", source]
            for include in suite["includes"]:
                command += ["-I", include]
            command += suite.get("build_flags", [])
            command += ["-o", binary]
            _run(f"build {name}", command)
            _run(f"run {name}", [binary], env=test_env)

    print("run_all_tests: all suites passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
