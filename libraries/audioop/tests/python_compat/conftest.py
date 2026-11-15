"""Shared fixtures for audioop Python compatibility tests."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[4]
BUNDLE_PATH = ROOT / "libraries/audioop/tests/vectors/audioop_vectors.json"
CLI_SOURCE = ROOT / "libraries/audioop/mojo/cli.mojo"
MOJO_INCLUDE = ROOT / "libraries/audioop/mojo"
REFERENCE_PYTHON = ROOT / "libraries/audioop/python_reference/.venv/bin/python"
ORACLE_SCRIPT = ROOT / "libraries/audioop/python_reference/oracle_samples.py"


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
def audioop_cli(tmp_path_factory: pytest.TempPathFactory) -> Path:
    binary = tmp_path_factory.mktemp("bin") / "audioop_cli"
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
            "failed to build audioop CLI\n"
            f"command: {' '.join(command)}\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )
    return binary


@pytest.fixture(scope="session")
def sample_oracle():
    if not REFERENCE_PYTHON.exists():
        pytest.fail(
            "reference interpreter missing: create the isolated CPython 3.12 venv at "
            f"{REFERENCE_PYTHON.parent.parent}"
        )

    def run(*, decode: list[dict] | None = None, encode: list[dict] | None = None) -> dict:
        request = json.dumps({"decode": decode or [], "encode": encode or []})
        result = subprocess.run(
            [str(REFERENCE_PYTHON), str(ORACLE_SCRIPT)],
            input=request,
            capture_output=True,
            text=True,
            timeout=300,
            cwd=ROOT,
        )
        if result.returncode != 0:
            pytest.fail(
                f"reference oracle failed\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
            )
        return json.loads(result.stdout)

    return run
