"""E10: strided sample loops over a byte fragment.

Question: is an index-based loop over samples fast and safe enough, and can
in-place and out-of-place transforms share the same pattern?
"""

from std.collections import List


def scale_in_place(mut fragment: List[UInt8], width: Int, factor: Int32):
    var frames = len(fragment) // width
    for frame in range(frames):
        var base = frame * width
        # 16-bit little-endian for this experiment.
        var raw = UInt16(fragment[base]) | (UInt16(fragment[base + 1]) << 8)
        var value = Int32(Int16(raw))
        var scaled = value * factor
        if scaled > 32767:
            scaled = 32767
        elif scaled < -32768:
            scaled = -32768
        var result = UInt16(UInt32(Int32(scaled)) & 0xFFFF)
        fragment[base] = UInt8(result & 0xFF)
        fragment[base + 1] = UInt8(result >> 8)


def sum_frames(fragment: List[UInt8], width: Int) -> Int64:
    var total: Int64 = 0
    var frames = len(fragment) // width
    for frame in range(frames):
        var base = frame * width
        var raw = UInt16(fragment[base]) | (UInt16(fragment[base + 1]) << 8)
        total += Int64(Int32(Int16(raw)))
    return total


def main() raises:
    var data = List[UInt8](capacity=8)
    for value in range(4):
        var sample = Int16(value * 100)
        var raw = UInt16(UInt32(Int32(sample)) & 0xFFFF)
        data.append(UInt8(raw & 0xFF))
        data.append(UInt8(raw >> 8))

    assert sum_frames(data, 2) == 600
    scale_in_place(data, 2, 2)
    assert sum_frames(data, 2) == 1200
    print("E10 ok: index-based sample loops support in-place transforms")
