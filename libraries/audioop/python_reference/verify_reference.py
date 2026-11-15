"""Prove that the installed CPython 3.12 audioop matches pristine upstream source.

The distro ships ``audioop`` as a compiled extension. To rule out a silently
different build, this script loads a second module compiled by hand from the
official CPython 3.12.3 tarball (``Modules/audioop.c`` plus the generated
``Modules/clinic/audioop.c.h``) and compares it against the installed module on
every probe case.

Build the pristine module (already documented in
``docs/licensing-audit.md``)::

    gcc -shared -fPIC -O2 -I/usr/include/python3.12 \\
        -I /path/to/Python-3.12.3/Modules \\
        -DPyInit_audioop=PyInit_audioop_pristine \\
        /path/to/Python-3.12.3/Modules/audioop.c \\
        -o /tmp/audioop_pristine$EXT_SUFFIX

Then::

    libraries/audioop/python_reference/.venv/bin/python \\
        libraries/audioop/python_reference/verify_reference.py \\
        --module-path /tmp/audioop_pristine$EXT_SUFFIX

Exit status 0 means the two builds agree on every recorded case.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import probe_audioop  # noqa: E402


def load_module(name: str, path: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"verify_reference: cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    with probe_audioop.warnings.catch_warnings():
        probe_audioop.warnings.simplefilter("ignore", DeprecationWarning)
        spec.loader.exec_module(module)
    return module


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--module-path", required=True, help="pristine audioop .so")
    parser.add_argument("--report", type=argparse.FileType("w"), default=None)
    args = parser.parse_args(argv)

    installed = probe_audioop.require_reference()
    pristine = load_module("audioop_pristine", args.module_path)

    cases = probe_audioop.build_cases()
    left = probe_audioop.run_cases(installed, cases)
    right = probe_audioop.run_cases(pristine, cases)

    mismatches = []
    for a, b in zip(left, right, strict=True):
        if (
            not probe_audioop.enc_float_equal(a.get("result"), b.get("result"))
            or ("exception" in a) != ("exception" in b)
            or (
                "exception" in a
                and (a["exception"]["type"], a["exception"]["message"])
                != (b["exception"]["type"], b["exception"]["message"])
            )
        ):
            mismatches.append({"id": a["id"], "installed": a, "pristine": b})

    report = {
        "installed": installed.__file__,
        "pristine": Path(args.module_path).resolve().as_posix(),
        "cases": len(cases),
        "mismatches": len(mismatches),
        "details": mismatches,
    }
    if args.report:
        json.dump(report, args.report, indent=1, sort_keys=True)
        args.report.write("\n")
    print(
        f"verify_reference: {len(cases)} cases, {len(mismatches)} mismatches "
        f"({Path(installed.__file__).name} vs {Path(args.module_path).name})"
    )
    for detail in mismatches[:5]:
        print(f"  MISMATCH {detail['id']}: {detail['installed']} != {detail['pristine']}")
    return 1 if mismatches else 0


if __name__ == "__main__":
    raise SystemExit(main())
