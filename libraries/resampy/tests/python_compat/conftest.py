"""Shared fixtures for Resampy Phase 3 Python compatibility tests."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[4]
CLI_SOURCE = ROOT / "libraries" / "resampy" / "mojo" / "cli.mojo"
MOJO_INCLUDE = ROOT / "libraries" / "resampy" / "mojo"
VECTORS = ROOT / "libraries" / "resampy" / "tests" / "vectors" / "representation_vectors.json"
FILTER_META = ROOT / "libraries" / "resampy" / "resources" / "synthetic" / "synthetic_filter.json"
FILTER_BIN = ROOT / "libraries" / "resampy" / "resources" / "synthetic" / "synthetic_filter.bin"


def _mojo_binary() -> str:
    venv_mojo = ROOT / ".venv" / "bin" / "mojo"
    if venv_mojo.exists():
        return str(venv_mojo)
    found = shutil.which("mojo")
    if not found:
        pytest.fail("mojo compiler not found (.venv/bin/mojo or PATH)")
    return found


@pytest.fixture(scope="session")
def resampy_cli(tmp_path_factory: pytest.TempPathFactory) -> Path:
    existing = os.environ.get("RESAMPY_CLI")
    if existing and Path(existing).exists():
        return Path(existing)
    binary = tmp_path_factory.mktemp("bin") / "resampy_cli"
    command = [
        _mojo_binary(),
        "build",
        str(CLI_SOURCE),
        "-I",
        str(MOJO_INCLUDE),
        "--fp-mode",
        "contract=off",
        "-o",
        str(binary),
    ]
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=600)
    if result.returncode != 0:
        pytest.fail(
            f"failed to build resampy CLI\ncommand: {' '.join(command)}\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
    return binary


@pytest.fixture(scope="session")
def vectors_bundle() -> dict:
    return json.loads(VECTORS.read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def filter_resource() -> tuple[bytes, bytes]:
    return FILTER_META.read_bytes(), FILTER_BIN.read_bytes()
