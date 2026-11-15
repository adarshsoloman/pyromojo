"""E01: UInt8 byte buffers, slicing to Span, iteration, copy independence.

Question: can Mojo 1.2.0 hold and traverse a raw byte buffer the way
audioop's Py_buffer does?
"""

from std.collections import List


def main() raises:
    var buf = List[UInt8](capacity=8)
    buf.resize(4, 0)
    for i in range(4):
        buf[i] = UInt8(i * 10)
    assert buf[0] == 0
    assert buf[3] == 30

    var view = buf[0:4]
    assert len(view) == 4
    assert view[2] == 20

    var total: Int = 0
    for byte in view:
        total += Int(byte)
    assert total == 60

    # A copy is independent; a slice aliases.
    var duplicate = buf.copy()
    duplicate[0] = 99
    assert buf[0] == 0
    assert duplicate[0] == 99
    buf[1] = 77
    assert view[1] == 77

    print("E01 ok: len=", len(buf), "total=", total, "copy-independent=True")
