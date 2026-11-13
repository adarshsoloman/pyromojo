#!/usr/bin/env python3
"""Phase 0 follow-up probe: edge cases, cross-endianness rules, API details.

Run with::

    .venv/bin/python libraries/bitarray/experiments/probe_edge_cases.py
"""

from __future__ import annotations

import copy

from bitarray import bitarray, frozenbitarray


def show(label: str, value: object) -> None:
    print(f"{label}: {value!r}")


def attempt(label: str, fn) -> None:
    try:
        result = fn()
    except Exception as exc:  # noqa: BLE001 - deliberate exception probe
        print(f"{label}: RAISED {type(exc).__name__}: {exc}")
    else:
        print(f"{label}: {result!r}")


def section(title: str) -> None:
    print(f"\n== {title} ==")


def main() -> int:
    section("exports and defaults")
    import bitarray as bitarray_module

    print(f"__all__: {getattr(bitarray_module, '__all__', None)}")
    show("default endian kwarg omitted", bitarray().endian)
    show("frozen default endian", frozenbitarray().endian)

    section("cross-endianness rules")
    big = bitarray("101", endian="big")
    little = bitarray("101", endian="little")
    for label, fn in [
        ("eq", lambda: big == little),
        ("ne", lambda: big != little),
        ("lt", lambda: big < little),
        ("concat", lambda: (big + little).to01()),
        ("iadd", lambda: (lambda x: (x.__iadd__(little), x.to01()))(big.copy())),
        ("and", lambda: big & little),
        ("or", lambda: big | little),
        ("xor", lambda: big ^ little),
        ("extend", lambda: (lambda x: (x.extend(little), x.to01()))(big.copy())),
    ]:
        attempt(f"mixed-endian {label}", fn)
    attempt("compare big vs str", lambda: big == "101")
    attempt("compare big vs int", lambda: big == 5)
    attempt("lt vs str", lambda: big < "101")
    attempt("hash mutable", lambda: hash(big))
    print(f"frozen hash stable: {hash(frozenbitarray('101')) == hash(frozenbitarray('101'))}")

    section("truthiness and emptiness")
    print(f"bool(empty)={bool(bitarray())} bool(all-zero)={bool(bitarray('000'))}")
    print(f"bool(nonempty)={bool(bitarray('001'))} len(empty)={len(bitarray())}")

    section("count variants")
    bits = bitarray("10110101")
    print(f"count()={bits.count()} count(1)={bits.count(1)} count(True)={bits.count(True)}")
    print(f"count(0)={bits.count(0)} count(False)={bits.count(False)}")
    print(f"count(1,2)={bits.count(1, 2)} count(1,2,6)={bits.count(1, 2, 6)}")
    print(f"count(1,0,-8)={bits.count(1, 0, -8)}")
    attempt("count step 0", lambda: bits.count(1, 0, 8, 0))
    attempt("count bad type", lambda: bits.count("1"))

    section("find/index/search bounds")
    bits = bitarray("00100100")
    print(f"find sub: {bits.find(bitarray('100'))}")
    print(f"find sub start=3: {bits.find(bitarray('100'), 3)}")
    print(f"find sub start beyond: {bits.find(bitarray('100'), 100)}")
    print(f"find empty pattern: {bits.find(bitarray(''))}")
    print(f"find single int: {bits.find(1)}")
    attempt("find bad pattern", lambda: bits.find("10"))
    print(f"index stop hit: {bits.index(1, 0, 3)}")
    attempt("index stop miss", lambda: bits.index(1, 0, 2))
    attempt("index missing in range", lambda: bits.index(1, 0, 1))
    print(f"search all: {list(bits.search(bitarray('00')))}")
    print(f"search start: {list(bits.search(bitarray('00'), 3))}")
    show("index value 0", bitarray("101").index(0))

    section("extend/concat aliasing and types")
    bits = bitarray("10")
    bits.extend(bits)
    print(f"extend self: {bits.to01()}")
    bits = bitarray("10") * 3
    print(f"mul: {bits.to01()}")
    attempt("mul negative", lambda: bitarray("10") * -1)
    bits = bitarray("10")
    bits *= 0
    print(f"imul 0: {bits.to01()!r} len={len(bits)}")
    bits = bitarray("1")
    bits += "01"
    print(f"iadd str: {bits.to01()}")
    attempt("add str", lambda: bitarray("1") + 1)
    bits = bitarray("101")
    show("contains 1", 1 in bits)
    show("contains sub-bitarray", bitarray("01") in bits)
    attempt("contains str", lambda: "01" in bits)

    section("insert/pop/remove/rotate edges")
    bits = bitarray("")
    bits.insert(0, 1)
    print(f"insert into empty: {bits.to01()}")
    bits = bitarray("101")
    bits.insert(-1, 0)
    print(f"insert negative index: {bits.to01()}")
    print(f"pop negative: {bitarray('101').pop(-1)}")
    attempt("pop out of range", lambda: bitarray("1").pop(5))
    print(f"remove returns: {bitarray('101').remove(0)}")
    rotated = bitarray("101")
    rotated.rotate(0)
    print(f"rotate 0: {rotated.to01()}")
    rotated = bitarray("101")
    rotated.rotate(100)
    print(f"rotate huge: {rotated.to01()}")
    rotated = bitarray("")
    rotated.rotate(3)
    print(f"rotate empty: {rotated.to01()!r}")
    show("clear returns", bitarray("1").clear())

    section("copy semantics and readonly")
    original = bitarray("101")
    alias = original.copy()
    alias[0] = 0
    print(f"copy independent: original={original.to01()} copy={alias.to01()}")
    print(f"deepcopy: {copy.deepcopy(original).to01()}")
    print(f"explicit copy ctor: {bitarray(original).to01()}")
    readonly = bitarray(buffer=b"\xa0")
    print(f"readonly from bytes buffer: {readonly.readonly}")
    attempt("readonly append", lambda: readonly.append(1))
    attempt("readonly setitem", lambda: readonly.__setitem__(0, 0))
    print(f"readonly read ok: {readonly.to01()} len={len(readonly)}")
    show("buffer_info readonly", readonly.buffer_info().readonly)

    section("shifts preserve length (bits fall off, zeros fill in)")
    for text in ("11001010", "1" * 64, "1" * 65, "101" * 100):
        bits = bitarray(text)
        ok = True
        for shift in (0, 1, 63, 64, 65, 1000, 10**6):
            if len(bits << shift) != len(bits) or len(bits >> shift) != len(bits):
                print(f"LENGTH VIOLATION len={len(bits)} shift={shift}")
                ok = False
                break
        if ok:
            print(f"length preserved for len {len(bits)}")
    print(f"shift by len: {(bitarray('101') << 3).to01()!r}")
    print(f"right shift by len: {(bitarray('101') >> 3).to01()!r}")
    print(f"huge shift all zeros: {set(bitarray('1' * 10) << 10**6) == {0}}")
    mixed = (bitarray("111", endian="big") << 2).to01()
    print(f"big-endian shift left 2: {mixed}")
    mixed = (bitarray("111", endian="little") << 2).to01()
    print(f"little-endian shift left 2: {mixed}")

    section("sort details")
    show("sort empty", bitarray("").tolist())
    show("sort single", bitarray("0").tolist())
    show("no byteswap method (util only)", hasattr(bitarray("10101010"), "byteswap"))
    from bitarray.util import byteswap

    swapped = bitarray("10101010")
    print(f"util.byteswap in place: {byteswap(swapped)} -> {swapped.to01()!r}")

    section("__all__ and module surface")
    import bitarray as bitarray_module

    print(f"module __all__: {getattr(bitarray_module, '__all__', 'ABSENT')}")
    print(f"has BufferInfo: {hasattr(bitarray_module, 'BufferInfo')}")
    print(f"has test: {hasattr(bitarray_module, 'test')}")
    attempt("call test()", lambda: bitarray_module.test(verbosity=0))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
