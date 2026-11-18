"""Phase 3.1 Python compat: type-enforced immutability of Signal.view()."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
FIXTURE = ROOT / "libraries/resampy/tests/mojo/compile_fail_view_write.mojo"
MOJO_INCLUDE = ROOT / "libraries/resampy/mojo"


def _mojo_binary() -> str:
    venv_mojo = ROOT / ".venv" / "bin" / "mojo"
    if venv_mojo.exists():
        return str(venv_mojo)
    found = shutil.which("mojo")
    if found:
        return found
    raise AssertionError("mojo compiler not found")


def test_signal_view_write_is_compile_error(tmp_path) -> None:
    """The read-only view is enforced by Mojo, not merely by convention."""
    binary = tmp_path / "must_not_build"
    result = subprocess.run(
        [
            _mojo_binary(),
            "build",
            str(FIXTURE),
            "-I",
            str(MOJO_INCLUDE),
            "--fp-mode",
            "contract=off",
            "-o",
            str(binary),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert result.returncode != 0, "writing through Signal.view() compiled unexpectedly"
    assert not binary.exists(), "invalid fixture produced a binary"
    assert "mutable in assignment" in (result.stdout + result.stderr) or "error" in (
        result.stdout + result.stderr
    )
