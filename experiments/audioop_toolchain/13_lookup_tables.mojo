"""E13: compile-time and runtime lookup tables.

Question: how do we express audioop's static tables (_st_ulaw2linear16,
stepsizeTable, indexTable, seg_aend, seg_uend) in Mojo 1.2.0?
"""

from std.collections import List
from std.utils import StaticTuple


comptime STEPSIZES: StaticTuple[Int32, 8] = StaticTuple[Int32, 8](
    7, 8, 9, 10, 11, 12, 13, 14
)
comptime CHANGES: StaticTuple[Int32, 8] = StaticTuple[Int32, 8](
    -1, -1, -1, -1, 2, 4, 6, 8
)


def table_lookup(index: Int) -> Int32:
    return STEPSIZES[index] + CHANGES[index]


def main() raises:
    # comptime table reads are exact and need no runtime allocation.
    assert STEPSIZES[0] == 7
    assert table_lookup(7) == 22
    assert table_lookup(4) == 13

    # A runtime table for values produced at run time.
    var runtime = List[Int32](capacity=4)
    runtime.append(100)
    runtime.append(-100)
    runtime.append(0)
    runtime.append(1)
    var total: Int32 = 0
    for value in runtime:
        total += value
    assert total == 1

    # A 256-entry u-law decode table can be generated once at comptime.
    var generated = generate_ulaw_table()
    assert len(generated) == 256
    assert generated[0] == -32124
    assert generated[255] == 0

    print("E13 ok: comptime StaticTuple and runtime List tables both usable")


def generate_ulaw_table() -> List[Int32]:
    var table = List[Int32](capacity=256)
    for index in range(256):
        var u = ~index & 0xFF
        var sign = u & 0x80
        var exponent = (u >> 4) & 0x07
        var mantissa = u & 0x0F
        var value = ((mantissa << 3) + 0x84) << exponent
        value -= 0x84
        if sign != 0:
            value = -value
        table.append(Int32(value))
    return table^
