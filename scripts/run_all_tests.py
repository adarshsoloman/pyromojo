"""Run every repository test suite with the pinned toolchain.

From the repository root::

    uv sync --extra dev
    .venv/bin/python scripts/run_all_tests.py

Steps, in order: ruff lint, ruff format check, golden-vector drift check,
the full pytest suite, then each native Mojo test executable (built once
into ``build/`` and run). The first failing step stops the run with exit 1
and prints the failing command plus its output tail; nothing is skipped
silently. The Mojo compiler must report version 1.2.x; anything else fails
instead of falling back to a system toolchain.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUILD_DIR = ROOT / "build"
MOJO_TESTS = [
    "test_depth",
    "test_integer_codec",
    "test_scalar_codec",
    "test_container_codec",
    "test_extension_codec",
    "test_regressions",
    "test_generated_vectors",
]


def _resolve_tool(name: str) -> list[str]:
    venv_tool = ROOT / ".venv" / "bin" / name
    if venv_tool.exists():
        return [str(venv_tool)]
    if shutil.which("uv") is not None:
        return ["uv", "run", name]
    sys.exit(f"run_all_tests: cannot find {name} (.venv/bin/{name} or uv)")


def _check_mojo(mojo: list[str]) -> None:
    result = subprocess.run([*mojo, "--version"], capture_output=True, text=True, cwd=ROOT)
    version = (result.stdout + result.stderr).strip()
    print(f"mojo toolchain: {' '.join(mojo)} -> {version}")
    if result.returncode != 0 or "Mojo 1.2." not in version:
        sys.exit(
            "run_all_tests: need the pinned Mojo 1.2.x toolchain "
            f"(.venv/bin/mojo or `uv run mojo`), got: {version!r}"
        )


def _run(label: str, command: list[str]) -> None:
    print(f"--- {label}: {' '.join(command)}")
    result = subprocess.run(command, capture_output=True, text=True, cwd=ROOT)
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
    _run("pytest", [*pytest, "-q"])

    BUILD_DIR.mkdir(exist_ok=True)
    for name in MOJO_TESTS:
        source = f"libraries/msgpack/tests/mojo/{name}.mojo"
        binary = str(BUILD_DIR / name)
        _run(
            f"build {name}",
            [
                *mojo,
                "build",
                source,
                "-I",
                "libraries/msgpack/mojo",
                "-I",
                "libraries/msgpack/tests/mojo",
                "-o",
                binary,
            ],
        )
        _run(f"run {name}", [binary])

    print("run_all_tests: all suites passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
