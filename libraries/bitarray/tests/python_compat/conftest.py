"""Shared fixtures for bitarray Python compatibility tests."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[4]
BUNDLE_PATH = ROOT / "libraries/bitarray/tests/vectors/bitarray_vectors.json"
CLI_SOURCE = ROOT / "libraries/bitarray/mojo/cli.mojo"
MOJO_INCLUDE = ROOT / "libraries/bitarray/mojo"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

REFERENCE_DIR = ROOT / "libraries/bitarray/python_reference"
if str(REFERENCE_DIR) not in sys.path:
    sys.path.insert(0, str(REFERENCE_DIR))


def _mojo_binary() -> str:
    venv_mojo = ROOT / ".venv/bin/mojo"
    if venv_mojo.exists():
        return str(venv_mojo)
    found = shutil.which("mojo")
    if not found:
        pytest.fail("mojo compiler not found (.venv/bin/mojo or PATH)")
    return found


@pytest.fixture(scope="session")
def vectors_bundle() -> dict:
    return json.loads(BUNDLE_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def bitarray_cli(tmp_path_factory: pytest.TempPathFactory) -> Path:
    binary = tmp_path_factory.mktemp("bin") / "bitarray_cli"
    command = [
        _mojo_binary(),
        "build",
        str(CLI_SOURCE),
        "-I",
        str(MOJO_INCLUDE),
        "-o",
        str(binary),
    ]
    result = subprocess.run(
        command,
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=600,
    )
    if result.returncode != 0:
        pytest.fail(
            "failed to build bitarray CLI\n"
            f"command: {' '.join(command)}\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )
    return binary
