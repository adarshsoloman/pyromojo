#!/usr/bin/env python3
"""Phase 3 library-local test runner.

Builds every native Mojo test and the CLI with ``--fp-mode contract=off``
(Phase 2 requirement: default ``contract=fast`` can shift Float64 results by
1 ULP). Then runs each native suite and the Python compatibility pytest suite.

This runner is local to ``libraries/resampy`` and does not modify the global
``scripts/run_all_tests.py``. The global runner independently includes the
Resampy vector drift check, CLI build, and native/Python suites. Run from the
repository root::

    .venv/bin/python libraries/resampy/tests/run_phase3_tests.py
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
MOJO = ROOT / ".venv" / "bin" / "mojo"
BUILD = ROOT / "build" / "resampy_phase3"
RESAMPY_TMP = Path("/tmp/pyromojo_resampy_phase3")
MOJO_INCLUDE = ROOT / "libraries" / "resampy" / "mojo"
TESTS_INCLUDE = ROOT / "libraries" / "resampy" / "tests" / "mojo"
TESTS_DIR = TESTS_INCLUDE
CLI_SOURCE = MOJO_INCLUDE / "cli.mojo"
PYTEST = ROOT / ".venv" / "bin" / "pytest"

NATIVE_TESTS = [
    "test_signal",
    "test_output",
    "test_float_codec",
    "test_json_codec",
    "test_coefficients",
    "test_numerical_compare",
    "test_golden_vector",
    "test_cli",
    "test_resample",
]

FP_FLAGS = ["--fp-mode", "contract=off"]


def run(label: str, command: list[str], env: dict[str, str] | None = None) -> None:
    print(f"--- {label}: {' '.join(command)}")
    merged = os.environ.copy()
    if env:
        merged.update(env)
    result = subprocess.run(command, cwd=ROOT, env=merged, capture_output=True, text=True)
    if result.returncode != 0:
        print((result.stdout + result.stderr)[-4000:])
        raise SystemExit(f"FAILED: {label} (exit {result.returncode})")
    tail = (result.stdout + result.stderr).strip()[-600:]
    if tail:
        print(tail)


def main() -> int:
    if not MOJO.exists():
        raise SystemExit(f"mojo not found at {MOJO}")
    BUILD.mkdir(parents=True, exist_ok=True)
    RESAMPY_TMP.mkdir(parents=True, exist_ok=True)

    cli_binary = BUILD / "resampy_cli"
    run(
        "build resampy CLI (fp contract=off)",
        [
            str(MOJO),
            "build",
            str(CLI_SOURCE),
            "-I",
            str(MOJO_INCLUDE),
            *FP_FLAGS,
            "-o",
            str(cli_binary),
        ],
    )

    env = {"RESAMPY_CLI": str(cli_binary)}
    for name in NATIVE_TESTS:
        source = TESTS_DIR / f"{name}.mojo"
        binary = BUILD / f"resampy_{name}"
        run(
            f"build {name} (fp contract=off)",
            [
                str(MOJO),
                "build",
                str(source),
                "-I",
                str(MOJO_INCLUDE),
                "-I",
                str(TESTS_INCLUDE),
                *FP_FLAGS,
                "-o",
                str(binary),
            ],
        )
        run(f"run {name}", [str(binary)], env=env)

    compat = ROOT / "libraries" / "resampy" / "tests" / "python_compat"
    pytest_cmd = str(PYTEST) if PYTEST.exists() else (shutil.which("pytest") or "pytest")
    run("python compatibility tests", [pytest_cmd, "-q", str(compat)], env=env)
    print("run_phase3_tests: ALL PASSED (fp-mode=contract=off)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
