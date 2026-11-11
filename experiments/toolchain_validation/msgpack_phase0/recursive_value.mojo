"""Phase 0 probe: recursive Value built on List[Self].

Covers construction, nested arrays/maps, copy, move, and destruction.
No msgpack logic; this only validates the Mojo type model.
"""

from std.collections import List


comptime TAG_NIL: UInt8 = 0
comptime TAG_INT: UInt8 = 1
comptime TAG_ARRAY: UInt8 = 2
comptime TAG_MAP: UInt8 = 3


struct Value(Deinitable, Copyable, Movable):
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
    def int(value: UInt64) -> Self:
        return Self(TAG_INT, value, List[Self]())

    @staticmethod
    def array(var items: List[Self]) -> Self:
        return Self(TAG_ARRAY, 0, items^)

    @staticmethod
    def map(var pairs: List[Self]) -> Self:
        return Self(TAG_MAP, 0, pairs^)


def depth(value: Value) -> Int:
    if value.tag != TAG_ARRAY and value.tag != TAG_MAP:
        return 1
    var best = 0
    for child in value.kids:
        var d = depth(child)
        if d > best:
            best = d
    return best + 1


def collect_leaves(value: Value, mut out: List[UInt64]):
    if value.tag == TAG_INT:
        out.append(value.num)
        return
    for child in value.kids:
        collect_leaves(child, out)


def run_construction_and_nesting():
    var leaves = List[Value]()
    leaves.append(Value.int(10))
    leaves.append(Value.int(20))
    var inner = Value.array(leaves^)

    var outer_items = List[Value]()
    outer_items.append(inner.copy())
    outer_items.append(Value.int(30))
    var outer = Value.array(outer_items^)

    assert outer.tag == TAG_ARRAY
    assert len(outer.kids) == 2
    assert outer.kids[0].tag == TAG_ARRAY
    assert len(outer.kids[0].kids) == 2
    assert outer.kids[0].kids[1].num == 20
    assert outer.kids[1].num == 30
    assert depth(outer) == 3

    # Map uses flat [key, value, key, value] storage.
    var pairs = List[Value]()
    pairs.append(Value.int(0))
    pairs.append(inner^)
    pairs.append(Value.int(1))
    pairs.append(outer.copy())
    var m = Value.map(pairs^)
    assert m.tag == TAG_MAP
    assert len(m.kids) == 4
    assert m.kids[2].num == 1
    assert m.kids[3].tag == TAG_ARRAY
    assert depth(m) == 4

    print("nesting: PASS (array depth 3, map depth 4)")


def run_copy():
    var items = List[Value]()
    items.append(Value.int(1))
    var inner = Value.array(items^)

    var root_items = List[Value]()
    root_items.append(inner^)
    var original = Value.array(root_items^)

    var duplicated = original.copy()

    duplicated.kids[0].kids.append(Value.int(2))
    assert len(original.kids[0].kids) == 1, "copy aliased nested list"
    assert len(duplicated.kids[0].kids) == 2
    assert depth(original) == 2
    assert depth(duplicated) == 2

    print("copy: PASS (deep copy, no aliasing)")


def run_move():
    var items = List[Value]()
    items.append(Value.int(7))
    items.append(Value.int(8))
    var child = Value.array(items^)

    var holders = List[Value]()
    holders.append(child^)
    var moved = Value.array(holders^)

    assert moved.kids[0].tag == TAG_ARRAY
    assert len(moved.kids[0].kids) == 2
    assert moved.kids[0].kids[0].num == 7
    assert moved.kids[0].kids[1].num == 8

    var leaves = List[UInt64]()
    collect_leaves(moved, leaves)
    assert len(leaves) == 2
    assert leaves[0] == 7
    assert leaves[1] == 8

    print("move: PASS (nested structure intact after transfer)")


def build_and_drop(rounds: Int):
    for _ in range(rounds):
        var items = List[Value]()
        for i in range(64):
            items.append(Value.int(UInt64(i)))
        var node = Value.array(items^)
        assert len(node.kids) == 64


def run_destruction():
    build_and_drop(10_000)
    print("destruction: PASS (10,000 nested values constructed and dropped)")


def main() raises:
    run_construction_and_nesting()
    run_copy()
    run_move()
    run_destruction()
    print("recursive_value: PASS")
