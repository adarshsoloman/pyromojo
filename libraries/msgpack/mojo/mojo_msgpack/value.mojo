"""MessagePack value model used by the Mojo implementation and its vectors.

The model is deliberately flat: scalars live in fixed fields, byte payloads in
``data``, and nested values in ``kids`` (map entries are stored as alternating
key/value children). This keeps the recursive type cheap to copy and makes the
depth guard a single traversal shared by encoder and decoder.
"""

from std.collections import List


comptime VALUE_NIL: UInt8 = 0
comptime VALUE_BOOL: UInt8 = 1
comptime VALUE_INT: UInt8 = 2
comptime VALUE_FLOAT32: UInt8 = 3
comptime VALUE_FLOAT64: UInt8 = 4
comptime VALUE_STR: UInt8 = 5
comptime VALUE_BIN: UInt8 = 6
comptime VALUE_ARRAY: UInt8 = 7
comptime VALUE_MAP: UInt8 = 8
comptime VALUE_EXT: UInt8 = 9
comptime VALUE_TIMESTAMP: UInt8 = 10
comptime VALUE_UINT: UInt8 = 11

comptime DEFAULT_MAX_DEPTH: Int = 128
comptime DEFAULT_MAX_CONTAINER_ITEMS: Int = 1_000_000


struct Value(Deinitable, Copyable, Movable):
    """A MessagePack value with an explicit recursion-depth guard.

    ``VALUE_INT`` stores a signed two's-complement bit pattern in ``int_bits``;
    ``VALUE_UINT`` stores an unsigned pattern. ``VALUE_TIMESTAMP`` stores signed
    seconds in ``int_bits`` and nanoseconds in
    ``nsec``. ``VALUE_EXT`` stores the extension code in ``ext_code`` and its
    payload in ``data``. ``VALUE_ARRAY`` children are elements;
    ``VALUE_MAP`` children are ordered key/value pairs.
    """

    var kind: UInt8
    var int_bits: UInt64
    var nsec: UInt32
    var ext_code: Int8
    var data: List[UInt8]
    var kids: List[Self]

    def __init__(out self):
        self.kind = VALUE_NIL
        self.int_bits = 0
        self.nsec = 0
        self.ext_code = 0
        self.data = List[UInt8]()
        self.kids = List[Self]()

    def __copyinit__(out self, other: Self):
        self.kind = other.kind
        self.int_bits = other.int_bits
        self.nsec = other.nsec
        self.ext_code = other.ext_code
        self.data = List[UInt8](copy=other.data)
        self.kids = List[Self](copy=other.kids)

    def __moveinit__(out self, deinit other: Self):
        self.kind = other.kind
        self.int_bits = other.int_bits
        self.nsec = other.nsec
        self.ext_code = other.ext_code
        self.data = other.data^
        self.kids = other.kids^

    def __deinit__(deinit self):
        # ponytail: fields are destroyed after this body, which recursively
        # releases ``kids``. Measured safe to 100k; callers still depth-guard.
        pass

    @staticmethod
    def nil() -> Self:
        return Self()

    @staticmethod
    def bool(value: Bool) -> Self:
        var result = Self()
        result.kind = VALUE_BOOL
        result.int_bits = UInt64(1) if value else UInt64(0)
        return result^

    @staticmethod
    def integer(value: Int64) -> Self:
        var result = Self()
        result.kind = VALUE_INT
        result.int_bits = UInt64(value.to_bits())
        return result^

    @staticmethod
    def unsigned(value: UInt64) -> Self:
        var result = Self()
        result.kind = VALUE_UINT
        result.int_bits = value
        return result^

    @staticmethod
    def float32(bits: UInt32) -> Self:
        var result = Self()
        result.kind = VALUE_FLOAT32
        result.int_bits = UInt64(bits)
        return result^

    @staticmethod
    def float64(value: Float64) -> Self:
        var result = Self()
        result.kind = VALUE_FLOAT64
        result.int_bits = UInt64(value.to_bits())
        return result^

    @staticmethod
    def float64_bits(bits: UInt64) -> Self:
        var result = Self()
        result.kind = VALUE_FLOAT64
        result.int_bits = bits
        return result^

    @staticmethod
    def string(var text: String) -> Self:
        var result = Self()
        result.kind = VALUE_STR
        result.data = List[UInt8](capacity=text.byte_length())
        for byte in text.as_bytes():
            result.data.append(byte)
        return result^

    @staticmethod
    def binary(var payload: List[UInt8]) -> Self:
        var result = Self()
        result.kind = VALUE_BIN
        result.data = payload^
        return result^

    @staticmethod
    def array(var items: List[Self]) -> Self:
        var result = Self()
        result.kind = VALUE_ARRAY
        result.kids = items^
        return result^

    @staticmethod
    def map(var pairs: List[Self]) -> Self:
        var result = Self()
        result.kind = VALUE_MAP
        result.kids = pairs^
        return result^

    @staticmethod
    def ext(code: Int8, var payload: List[UInt8]) -> Self:
        var result = Self()
        result.kind = VALUE_EXT
        result.ext_code = code
        result.data = payload^
        return result^

    @staticmethod
    def timestamp(seconds: Int64, nanoseconds: UInt32) -> Self:
        var result = Self()
        result.kind = VALUE_TIMESTAMP
        result.int_bits = UInt64(seconds.to_bits())
        result.nsec = nanoseconds
        return result^

    @staticmethod
    def array_repeat(var item: Self, count: Int) -> Self:
        var items = List[Self](capacity=count)
        for _ in range(count):
            items.append(item.copy())
        return Self.array(items^)

    @staticmethod
    def map_repeat(var key: Self, var value: Self, count: Int) -> Self:
        var pairs = List[Self](capacity=count * 2)
        for _ in range(count):
            pairs.append(key.copy())
            pairs.append(value.copy())
        return Self.map(pairs^)

    def is_nil(self) -> Bool:
        return self.kind == VALUE_NIL

    def is_integer(self) -> Bool:
        return self.kind == VALUE_INT or self.kind == VALUE_UINT

    def is_unsigned(self) -> Bool:
        return self.kind == VALUE_UINT

    def as_int64(self) -> Int64:
        return Int64(from_bits=self.int_bits)

    def as_uint64(self) -> UInt64:
        return self.int_bits

    def as_bool(self) -> Bool:
        return self.int_bits != 0

    def as_float32_bits(self) -> UInt32:
        return UInt32(self.int_bits)

    def as_float64_bits(self) -> UInt64:
        return self.int_bits

    def as_float64(self) -> Float64:
        return Float64(from_bits=self.int_bits)

    def depth(self) -> Int:
        """Return the nesting depth, where a scalar has depth 1."""
        var best = 0
        for index in range(len(self.kids)):
            var child_depth = self.kids[index].depth()
            if child_depth > best:
                best = child_depth
        return best + 1

    def check_depth(self, max_depth: Int) raises:
        """Raise when this value is nested deeper than ``max_depth``."""
        if max_depth < 1:
            raise Error("max_depth must be at least 1")
        var actual_depth = self.depth()
        if actual_depth > max_depth:
            raise Error(
                "MessagePack value depth "
                + String(actual_depth)
                + " exceeds max_depth "
                + String(max_depth)
            )


def make_array_chain(levels: Int, max_depth: Int) raises -> Value:
    """Build ``levels`` nested single-element arrays around an integer leaf.

    Used by depth-boundary tests and by future decoder limit checks. The
    result's depth is ``levels + 1`` and it is validated against ``max_depth``.
    """
    if levels < 0:
        raise Error("levels must be non-negative")
    var current = Value.integer(0)
    for _ in range(levels):
        var items = List[Value](capacity=1)
        items.append(current^)
        current = Value.array(items^)
    current.check_depth(max_depth)
    return current^
