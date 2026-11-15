"""E11: allocation patterns for exact-size output fragments.

Question: can the port allocate an output buffer of known length, fill it in
place, and avoid repeated growth?
"""

from std.collections import List


def passthrough(fragment: List[UInt8]) -> List[UInt8]:
    var result = List[UInt8](capacity=len(fragment))
    result.resize(len(fragment), 0)
    for i in range(len(fragment)):
        result[i] = fragment[i]
    return result^


def main() raises:
    var source = List[UInt8](capacity=16)
    source.resize(8, 0)
    for i in range(8):
        source[i] = UInt8(i + 1)

    var echo = passthrough(source)
    assert len(echo) == 8
    assert echo[0] == 1 and echo[7] == 8
    echo[0] = 42
    assert source[0] == 1

    var appended = List[UInt8]()
    for i in range(100):
        appended.append(UInt8(i & 0xFF))
    assert len(appended) == 100
    assert appended[99] == 99

    var filled = List[Int32](capacity=4)
    filled.resize(4, 7)
    assert len(filled) == 4
    assert filled[0] == 7 and filled[3] == 7

    print("E11 ok: exact-size allocation, immediate fill, growth and copies")
