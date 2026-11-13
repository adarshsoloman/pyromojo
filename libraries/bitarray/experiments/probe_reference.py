#!/usr/bin/env python3
"""Phase 0 black-box audit of the pinned bitarray reference.

This script only observes behaviour. Run with::

    .venv/bin/python libraries/bitarray/experiments/probe_reference.py

Findings are printed as ``key: value`` lines and captured verbatim into
``reference_probe_output.txt``.
"""

from __future__ import annotations

import importlib.metadata
import platform
import sys

import bitarray.util

import bitarray
from bitarray import frozenbitarray


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
    section("environment")
    print(f"python: {platform.python_version()} ({sys.implementation.name})")
    print(f"bitarray.__version__: {bitarray.__version__}")
    print(f"distribution version: {importlib.metadata.version('bitarray')}")
    print(f"bitarray module file: {bitarray.__file__}")
    print(f"default endian: {bitarray.get_default_endian()}")

    section("endianness: logical bits vs physical bytes")
    for endian in ("big", "little"):
        bits = bitarray.bitarray("11001010", endian=endian)
        print(f"{endian}: to01={bits.to01()} tobytes={bits.tobytes()!r}")
    for text, endian in [("1", "big"), ("1", "little"), ("10", "big"), ("10", "little")]:
        bits = bitarray.bitarray(text, endian=endian)
        info = bits.buffer_info()
        print(f"{text!r}/{endian}: bytes={bits.tobytes()!r} buffer_info={info}")
    # Cross-endianness equality and operations
    big = bitarray.bitarray("101", endian="big")
    little = bitarray.bitarray("101", endian="little")
    print(f"big==little (same logical bits): {big == little}")
    print(f"big.tobytes vs little.tobytes: {big.tobytes()!r} vs {little.tobytes()!r}")
    attempt("big & little", lambda: big & little)
    attempt("big == bytes", lambda: big == b"\xa0")
    print(f"big == bytearray of tobytes: {big == bytearray(big.tobytes())}")

    section("memory representation and padding")
    for text in ("", "1", "1010101", "10101010", "101010101"):
        for endian in ("big", "little"):
            bits = bitarray.bitarray(text, endian=endian)
            print(
                f"{text!r}/{endian}: len={len(bits)} nbytes={bits.nbytes} "
                f"padbits={bits.padbits} tobytes={bits.tobytes()!r}"
            )
    show("empty buffer_info", bitarray.bitarray().buffer_info())
    show("8-bit buffer_info", bitarray.bitarray("10101010").buffer_info())
    show("9-bit buffer_info", bitarray.bitarray("101010101").buffer_info())

    section("tobytes/frombytes roundtrip and padding")
    for text in ("", "1", "1010101", "10101010", "101010101", "1" * 64, "1" * 65):
        for endian in ("big", "little"):
            original = bitarray.bitarray(text, endian=endian)
            restored = bitarray.bitarray(endian=endian)
            restored.frombytes(original.tobytes())
            # frombytes appends whole bytes, so trim to original length for comparison
            trimmed = restored[: len(original)] if len(restored) > len(original) else restored
            print(
                f"{len(text)}b/{endian}: roundtrip_equal={trimmed == original} "
                f"restored_len={len(restored)}"
            )

    section("core operations: indexing and assignment")
    bits = bitarray.bitarray("10110")
    print(f"bits[0]={bits[0]!r} bits[-1]={bits[-1]!r} bits[2:4]={bits[2:4].to01()!r}")
    attempt("index out of range", lambda: bits[5])
    attempt("negative out of range", lambda: bits[-6])
    bits[0] = 0
    bits[-1] = 1
    print(f"after item assignment: {bits.to01()}")
    attempt("assign bad value", lambda: bits.__setitem__(0, 2))
    attempt("assign bad type", lambda: bits.__setitem__(0, "x"))
    bits[1:3] = bitarray.bitarray("00")
    print(f"after slice assignment: {bits.to01()}")
    show(
        "slice assign resizes shorter",
        bitarray.bitarray("101").__setitem__(slice(0, 2), bitarray.bitarray("1")) or "ok",
    )
    shrinking = bitarray.bitarray("101")
    shrinking[0:2] = bitarray.bitarray("1")
    print(f"after short slice assign: {shrinking.to01()!r} (resized like list)")
    growing = bitarray.bitarray("101")
    growing[0:1] = bitarray.bitarray("1111")
    print(f"after long slice assign: {growing.to01()!r} (resized like list)")
    show("step slice", bits[::2].to01())
    show("reversed slice", bits[::-1].to01())
    show("empty slice", bits[3:3].to01())

    section("core operations: mutation")
    bits = bitarray.bitarray("101")
    bits.append(0)
    print(f"append: {bits.to01()}")
    bits.extend("110")
    print(f"extend str: {bits.to01()}")
    bits.extend([1, 0])
    print(f"extend list: {bits.to01()}")
    bits.extend(bitarray.bitarray("11"))
    print(f"extend bitarray: {bits.to01()}")
    attempt("extend bad type", lambda: bits.extend(5))
    bits.insert(0, 1)
    print(f"insert at 0: {bits.to01()}")
    bits.insert(100, 0)
    print(f"insert past end appends: {bits.to01()}")
    attempt("insert bad index type", lambda: bits.insert("a", 1))
    show("pop default", bitarray.bitarray("101").pop())
    show("pop index 0", bitarray.bitarray("101").pop(0))
    attempt("pop empty", lambda: bitarray.bitarray().pop())
    bits = bitarray.bitarray("1011")
    bits.remove(0)
    print(f"remove first 0: {bits.to01()}")
    attempt("remove missing", lambda: bitarray.bitarray("111").remove(0))
    bits = bitarray.bitarray("101")
    bits.reverse()
    print(f"reverse odd: {bits.to01()}")
    bits = bitarray.bitarray("1010")
    bits.reverse()
    print(f"reverse even: {bits.to01()}")
    bits = bitarray.bitarray("101")
    bits.setall(0)
    print(f"setall 0: {bits.to01()}")
    bits.setall(True)
    print(f"setall True: {bits.to01()}")
    attempt("setall bad", lambda: bits.setall(2))
    bits = bitarray.bitarray("101")
    del bits[1]
    print(f"del index: {bits.to01()}")
    bits = bitarray.bitarray("10101")
    del bits[1:4]
    print(f"del slice: {bits.to01()}")
    bits = bitarray.bitarray("101")
    bits += bitarray.bitarray("01")
    print(f"concat +=: {bits.to01()}")
    print(f"concat +: {(bitarray.bitarray('10') + bitarray.bitarray('01')).to01()}")
    print(f"repeat *: {(bitarray.bitarray('10') * 3).to01()}")
    print(f"repeat 0: {(bitarray.bitarray('10') * 0).to01()}")
    print(f"concat str of bits works: {(bitarray.bitarray('10') + '01').to01()!r}")
    attempt("concat int errors", lambda: bitarray.bitarray("10") + 1)

    section("count, search, iteration, comparison")
    bits = bitarray.bitarray("101101")
    print(f"count()={bits.count()} count(0)={bits.count(0)} count(1, 2, 4)={bits.count(1, 2, 4)}")
    attempt("count bad value", lambda: bits.count(2))
    print(f"find 1: {bits.find(bitarray.bitarray('011'))} (expect 1)")
    print(f"find missing: {bits.find(bitarray.bitarray('0000'))}")
    print(f"index 1: {bits.index(1)}")
    print(f"search: {list(bits.search(bitarray.bitarray('10')))}")
    print(f"all: {bitarray.bitarray('111').all()} {bitarray.bitarray('101').all()}")
    print(f"any: {bitarray.bitarray('000').any()} {bitarray.bitarray('001').any()}")
    print(f"iter: {[int(v) for v in bitarray.bitarray('101')]}")
    print(f"tolist: {bitarray.bitarray('101').tolist()}")
    print(f"to01: {bitarray.bitarray('101').to01()!r}")
    print(f"eq: {bitarray.bitarray('101') == bitarray.bitarray('101')}")
    print(f"ne: {bitarray.bitarray('101') != bitarray.bitarray('100')}")
    print(f"lt: {bitarray.bitarray('100') < bitarray.bitarray('101')}")
    print(f"lt prefix: {bitarray.bitarray('10') < bitarray.bitarray('101')}")
    cross_endian = bitarray.bitarray("101", endian="big") == bitarray.bitarray(
        "101", endian="little"
    )
    print(f"endian in comparison: {cross_endian}")

    section("bitwise operations")
    left = bitarray.bitarray("1100")
    right = bitarray.bitarray("1010")
    print(f"and: {(left & right).to01()}")
    print(f"or: {(left | right).to01()}")
    print(f"xor: {(left ^ right).to01()}")
    print(f"invert: {(~left).to01()}")
    work = bitarray.bitarray("1100")
    work &= right
    print(f"iand: {work.to01()}")
    work = bitarray.bitarray("1100")
    work |= right
    print(f"ior: {work.to01()}")
    work = bitarray.bitarray("1100")
    work ^= right
    print(f"ixor: {work.to01()}")
    work = bitarray.bitarray("1100")
    work.invert()
    print(f"invert(): {work.to01()}")
    work.invert(1)
    print(f"invert(1): {work.to01()}")
    show("empty and", (bitarray.bitarray() & bitarray.bitarray()).to01())
    show("empty invert", (~bitarray.bitarray()).to01())
    attempt("and unequal lengths", lambda: bitarray.bitarray("11") & bitarray.bitarray("1"))
    attempt("or unequal lengths", lambda: bitarray.bitarray("11") | bitarray.bitarray("1"))
    attempt("xor unequal lengths", lambda: bitarray.bitarray("11") ^ bitarray.bitarray("1"))
    attempt("and non-bitarray", lambda: bitarray.bitarray("11") & 5)

    section("shifts")
    for shift in (0, 1, 7, 8, 9, 100):
        print(f"'10110011' << {shift}: {(bitarray.bitarray('10110011') << shift).to01()!r}")
        print(f"'10110011' >> {shift}: {(bitarray.bitarray('10110011') >> shift).to01()!r}")
    attempt("shift negative", lambda: bitarray.bitarray("11") << -1)
    attempt("shift non-int", lambda: bitarray.bitarray("11") << 1.5)
    work = bitarray.bitarray("11")
    work <<= 2
    print(f"ishift left: {work.to01()}")
    work >>= 1
    print(f"ishift right: {work.to01()}")
    print(f"empty shift: {(bitarray.bitarray() << 5).to01()!r}")
    print(f"big-int shift: {len(bitarray.bitarray('1' * 10) << 1000)} bits long")

    section("copy, sort, rotate, pack, unpack, fill")
    original = bitarray.bitarray("101")
    print(f"copy equal independent: {original.copy() == original}")
    attempt("fill", lambda: bitarray.bitarray("101").fill())
    filled = bitarray.bitarray("101")
    filled.extend("00000")
    print(f"fill pads to byte: {len(filled)} (extend does not auto-fill)")
    show("sort mixed", bitarray.bitarray("10110").__class__("10110").tolist())
    unsorted = bitarray.bitarray("10110")
    unsorted.sort(reverse=False)
    print(f"sort asc: {unsorted.to01()}")
    unsorted = bitarray.bitarray("10110")
    unsorted.sort(reverse=True)
    print(f"sort desc: {unsorted.to01()}")
    rotated = bitarray.bitarray("10011")
    rotated.rotate(2)
    print(f"rotate +2: {rotated.to01()}")
    rotated = bitarray.bitarray("10011")
    rotated.rotate(-2)
    print(f"rotate -2: {rotated.to01()}")
    packed = bitarray.bitarray()
    packed.pack(b"\x00\xff\x01")
    print(f"pack maps each byte to one bit: {packed.to01()!r} (0x00->0, else 1)")
    attempt("pack non-bytes", lambda: bitarray.bitarray().pack("abc"))
    single = bitarray.bitarray("101")
    print(f"unpack default map: {single.unpack()!r}")
    print(f"unpack custom map: {single.unpack(zero=b'A', one=b'B')!r}")
    attempt("unpack bad mapping", lambda: single.unpack(zero="A", one="B"))
    print(f"tolist roundtrip: {bitarray.bitarray([1, 0, 1]).to01()}")

    section("frozenbitarray")
    frozen = frozenbitarray("101")
    print(f"type: {type(frozen).__name__} hashable: {hash(frozen) == hash(frozenbitarray('101'))}")
    print(f"frozen == mutable equal: {frozen == bitarray.bitarray('101')}")
    attempt("frozen append", lambda: frozen.append(1))
    attempt("frozen item assign", lambda: frozen.__setitem__(0, 1))
    print(f"frozen ops ok: count={frozen.count()} to01={frozen.to01()!r}")

    section("constructor forms and errors")
    show("from str", bitarray.bitarray("101").to01())
    show("from list", bitarray.bitarray([True, False, True]).to01())
    show("from tuple", bitarray.bitarray((1, 0)).to01())
    show("from int repeat", bitarray.bitarray(5).to01())
    attempt("bad char", lambda: bitarray.bitarray("102"))
    attempt("from float", lambda: bitarray.bitarray(1.5))
    attempt("from dict", lambda: bitarray.bitarray({"a": 1}))
    show("endian kwarg only", bitarray.bitarray(endian="little").endian)
    attempt("bad endian", lambda: bitarray.bitarray(endian="middle"))
    show("default endian", bitarray.bitarray().endian)
    attempt("buffer str", lambda: bitarray.bitarray(buffer="abc"))
    show("buffer bytes", bitarray.bitarray(buffer=b"\xa0").to01())
    show("buffer bytearray", bitarray.bitarray(buffer=bytearray(b"\xa0")).to01())
    show("buffer memoryview", bitarray.bitarray(buffer=memoryview(b"\xa0")).to01())

    section("file and buffer interop")
    import io
    import tempfile

    bits = bitarray.bitarray("101010101")
    buffer = io.BytesIO()
    bits.tofile(buffer)
    print(f"tofile bytes: {buffer.getvalue()!r}")
    buffer.seek(0)
    restored = bitarray.bitarray()
    restored.fromfile(buffer)
    print(f"fromfile len: {len(restored)} to01: {restored.to01()!r}")
    with tempfile.NamedTemporaryFile() as tmp:
        bits.tofile(tmp)
        tmp.seek(0)
        restored2 = bitarray.bitarray()
        restored2.fromfile(tmp)
        print(f"real file roundtrip equal (trimmed): {restored2[: len(bits)] == bits}")
    reversed_bits = bitarray.bitarray("10000000")
    reversed_bits.bytereverse()
    show("bytereverse in place", reversed_bits.to01())
    partial = bitarray.bitarray("101")
    partial.bytereverse()
    show("bytereverse keeps len", len(partial))
    view = memoryview(bitarray.bitarray("10101010"))
    print(f"buffer protocol export: {bytes(view)!r}")
    show("buffer protocol import", bitarray.bitarray(buffer=b"\xf0").to01())
    show("clear", bitarray.bitarray("101").clear() or "cleared")
    cleared = bitarray.bitarray("101")
    cleared.clear()
    print(f"after clear len: {len(cleared)} nbytes: {cleared.nbytes}")

    section("util and bitfields modules")
    print(f"util names: {[n for n in dir(bitarray.util) if not n.startswith('_')]}")
    print(f"int2ba/ba2int roundtrip: {bitarray.util.ba2int(bitarray.util.int2ba(10))}")
    print(f"hex2ba/ba2hex: {bitarray.util.ba2hex(bitarray.util.hex2ba('ff'))!r}")
    print(f"zeros/ones: {bitarray.util.zeros(5).to01()!r} {bitarray.util.ones(3).to01()!r}")
    print(f"urandom len: {len(bitarray.util.urandom(16))}")
    serialized = bitarray.util.serialize(bitarray.bitarray("10101"))
    print(f"serialize/deserialize: {bitarray.util.deserialize(serialized).to01()!r}")
    print(f"strip right/trailing: {bitarray.util.strip(bitarray.bitarray('000101000')).to01()!r}")
    left_stripped = bitarray.util.strip(bitarray.bitarray("000101000"), "left")
    print(f"strip left/leading: {left_stripped.to01()!r}")
    show("subset bool", bitarray.util.subset(bitarray.bitarray("101"), bitarray.bitarray("111")))
    print(f"parity: {bitarray.util.parity(bitarray.bitarray('101'))}")
    print(f"count_and: {bitarray.util.count_and(bitarray.bitarray('11'), bitarray.bitarray('10'))}")
    from bitarray.bitfields import calcsize, compile, pack, unpack

    compiled = compile("u3 s5")
    packed_struct = compiled.pack(5, -3)
    print(f"bitfields struct width: {compiled.width} packed: {packed_struct.to01()!r}")
    print(f"bitfields unpack: {compiled.unpack(packed_struct)}")
    repacked = pack(">u4 s5", 10, -2)
    print(f"bitfields module fns: {repacked.to01()!r} {unpack('>u4 s5', repacked)}")
    print(f"calcsize u3s5: {calcsize('u3 s5')}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
