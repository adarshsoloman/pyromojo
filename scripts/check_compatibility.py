"""Check Python compatibility for one library or the whole repository.

From the repository root::

    uv sync --extra dev
    .venv/bin/python scripts/check_compatibility.py [--library msgpack]

Builds the native CLI once into ``build/`` and runs the Python
compatibility suite (C-backed and fallback reference decoders) plus the
golden-vector integrity tests. Only ``msgpack`` exists today; naming any
other library fails instead of silently passing. Exits non-zero with the
failing output on any incompatibility.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUILD_DIR = ROOT / "build"
KNOWN_LIBRARIES = ("msgpack",)


def _resolve_tool(name: str) -> list[str]:
    venv_tool = ROOT / ".venv" / "bin" / name
    if venv_tool.exists():
        return [str(venv_tool)]
    if shutil.which("uv") is not None:
        return ["uv", "run", name]
    sys.exit(f"check_compatibility: cannot find {name} (.venv/bin/{name} or uv)")


def _check_mojo(mojo: list[str]) -> None:
    result = subprocess.run([*mojo, "--version"], capture_output=True, text=True, cwd=ROOT)
    version = (result.stdout + result.stderr).strip()
    print(f"mojo toolchain: {' '.join(mojo)} -> {version}")
    if result.returncode != 0 or "Mojo 1.2." not in version:
        sys.exit(
            "check_compatibility: need the pinned Mojo 1.2.x toolchain "
            f"(.venv/bin/mojo or `uv run mojo`), got: {version!r}"
        )


def _run(label: str, command: list[str]) -> None:
    print(f"--- {label}: {' '.join(command)}")
    result = subprocess.run(command, capture_output=True, text=True, cwd=ROOT)
    output = (result.stdout + result.stderr).strip()
    if result.returncode != 0:
        print(output[-4000:])
        sys.exit(f"check_compatibility: FAILED: {label} (exit {result.returncode})")
    print(output[-500:] if output else "(no output)")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--library", default="all")
    args = parser.parse_args(argv)

    libraries = KNOWN_LIBRARIES if args.library == "all" else (args.library,)
    for library in libraries:
        if library not in KNOWN_LIBRARIES:
            sys.exit(
                f"check_compatibility: unknown library {library!r} "
                f"(known: {', '.join(KNOWN_LIBRARIES)})"
            )

    mojo = _resolve_tool("mojo")
    pytest = _resolve_tool("pytest")
    _check_mojo(mojo)

    BUILD_DIR.mkdir(exist_ok=True)
    for library in libraries:
        if library == "msgpack":
            _run(
                "build msgpack_cli",
                [
                    *mojo,
                    "build",
                    "libraries/msgpack/mojo/cli.mojo",
                    "-I",
                    "libraries/msgpack/mojo",
                    "-o",
                    str(BUILD_DIR / "msgpack_cli"),
                ],
            )
            _run(
                "msgpack compatibility",
                [*pytest, "-q", "libraries/msgpack/tests/python_compat"],
            )

    print("check_compatibility: all compatibility suites passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
