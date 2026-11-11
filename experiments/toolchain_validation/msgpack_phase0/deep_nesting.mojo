"""Phase 0 probe: how deep can recursive Value build, copy, walk, and drop?

Informs the decoder's max-depth guard. Run with a depth argument:
    /tmp/deep_nesting 100000
"""

from std.collections import List
from std.sys import argv


struct Chain(Deinitable, Copyable, Movable):
    var tag: UInt8
    var num: UInt64
    var kids: List[Self]

    def __init__(out self, tag: UInt8, num: UInt64, var kids: List[Self]):
        self.tag = tag
        self.num = num
        self.kids = kids^

    def __deinit__(deinit self):
        # ponytail: fields are destroyed automatically after this body.
        pass

    def __init__(out self, *, copy: Self):
        self.tag = copy.tag
        self.num = copy.num
        self.kids = List[Self](copy=copy.kids)

    @staticmethod
    def leaf(value: UInt64) -> Self:
        return Self(0, value, List[Self]())

    @staticmethod
    def node(var child: Self) -> Self:
        var items = List[Self](capacity=1)
        items.append(child^)
        return Self(1, 0, items^)


def make_chain(depth: Int) -> Chain:
    var current = Chain.leaf(0)
    for _ in range(depth):
        current = Chain.node(current^)
    return current^


def walk(value: Chain) -> Int:
    var count = 1
    if len(value.kids) > 0:
        count += walk(value.kids[0])
    return count


def main() raises:
    var depth = 10_000
    var args = argv()
    if len(args) > 1:
        depth = Int(String(args[1]))

    var root = make_chain(depth)
    assert walk(root) == depth + 1
    print("depth", depth, "build+walk: PASS")

    var do_copy = True
    if len(args) > 2 and String(args[2]) == "nocopy":
        do_copy = False
    if do_copy:
        var duplicated = root.copy()
        assert walk(duplicated) == depth + 1
        print("depth", depth, "deep copy: PASS")

    print("depth", depth, "deep_nesting: PASS")
