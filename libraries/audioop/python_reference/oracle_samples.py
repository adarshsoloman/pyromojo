"""Batch reference oracle for the Phase 1 sample representation layer.

Reads one JSON request from stdin and writes JSON to stdout. Runs only on
the pinned CPython 3.12 interpreter:

    libraries/audioop/python_reference/.venv/bin/python oracle_samples.py

Decode expectations come from ``audioop.getsample`` (the reference's
sample-level oracle; width/frame validation via ``audioop.max``). Encode
expectations are ``int.to_bytes(width, sys.byteorder, signed=True)`` and
are validated by decoding every value back through ``getsample``. There is
no reference encoder, so out-of-range values surface as ``OverflowError``
and the port applies its documented range check.
"""

from __future__ import annotations

import json
import sys

try:
    import audioop
except ImportError as exc:  # pragma: no cover - wrong interpreter guard
    raise SystemExit(
        "audioop is unavailable; run with libraries/audioop/python_reference/.venv/bin/python"
    ) from exc


def _decode_one(item: dict) -> dict:
    width = int(item["width"])
    fragment = bytes.fromhex(item["fragment_hex"])
    try:
        audioop.max(fragment, width)
        count = len(fragment) // width
        values = [audioop.getsample(fragment, width, index) for index in range(count)]
        return {"values": values}
    except Exception as exc:  # the reference defines these messages
        return {"error_type": type(exc).__name__, "error_message": str(exc)}


def _encode_one(item: dict) -> dict:
    width = int(item["width"])
    values = [int(value) for value in item["values"]]
    if width not in (1, 2, 3, 4):
        return {"error_type": "error", "error_message": "Size should be 1, 2, 3 or 4"}

    chunks = []
    try:
        for value in values:
            chunks.append(value.to_bytes(width, sys.byteorder, signed=True))
    except OverflowError:
        return {"error_type": "OverflowError", "error_message": "int too big to convert"}

    encoded = b"".join(chunks)
    decoded = [audioop.getsample(encoded, width, index) for index in range(len(values))]
    if decoded != values:
        raise AssertionError("encoded bytes do not round-trip through getsample")
    return {"result_hex": encoded.hex(), "values": decoded}


def main() -> int:
    request = json.load(sys.stdin)
    response = {
        "decode": [_decode_one(item) for item in request.get("decode", [])],
        "encode": [_encode_one(item) for item in request.get("encode", [])],
    }
    json.dump(response, sys.stdout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
