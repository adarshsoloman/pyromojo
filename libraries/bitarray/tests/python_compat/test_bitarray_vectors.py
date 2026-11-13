"""Golden-vector integrity: committed bundle versus the pinned reference.

The drift gate (``generate_vectors.py --check`` in the repo runner) pins
the committed files to the generator; these tests pin the generator
output itself to ``bitarray==3.12.3`` behavior: every case's packed
bytes, length, padding, and framed payload are recomputed from the
logical bits and compared.
"""

from __future__ import annotations

import struct
from pathlib import Path

import pytest

from bitarray import bitarray

BUNDLE_PATH = Path(__file__).resolve().parents[1] / "vectors" / "bitarray_vectors.json"


@pytest.fixture(scope="module")
def bundle() -> dict:
    import json

    data = json.loads(BUNDLE_PATH.read_text(encoding="utf-8"))
    assert data["reference"] == {"package": "bitarray", "version": "3.12.3"}
    return data


def test_bundle_has_expected_coverage(bundle: dict) -> None:
    cases = bundle["cases"]
    assert len(cases) > 200
    lengths = {case["nbits"] for case in cases}
    for n in (0, 1, 2, 3, 7, 8, 9, 15, 16, 17, 31, 32, 33, 63, 64, 65):
        assert n in lengths
    assert {case["endian"] for case in cases} == {"big", "little"}
    assert len({case["id"] for case in cases}) == len(cases)


def test_cases_match_reference(bundle: dict) -> None:
    for case in bundle["cases"]:
        a = bitarray(case["bits"], endian=case["endian"])
        assert len(a) == case["nbits"]
        assert a.padbits == case["padbits"]
        assert a.tobytes().hex() == case["packed_hex"]
        endian_id = 0 if case["endian"] == "big" else 1
        framed = struct.pack(">I", case["nbits"]) + bytes([endian_id]) + a.tobytes()
        assert framed.hex() == case["framed_hex"]
        # frombytes reconstruction (trimmed to the logical length).
        back = bitarray("", endian=case["endian"])
        back.frombytes(a.tobytes())
        assert back[: case["nbits"]].to01() == case["bits"]
