"""Phase 0 probe: float/int bit manipulation used by msgpack codecs."""

def f64_to_u64(value: Float64) -> UInt64:
    return UInt64(value.to_bits())


def u64_to_f64(bits: UInt64) -> Float64:
    return Float64(from_bits=bits)


def f32_to_u32(value: Float32) -> UInt32:
    return UInt32(value.to_bits())


def u32_to_f32(bits: UInt32) -> Float32:
    return Float32(from_bits=bits)


def check_f64(value: Float64, expected_bits: UInt64, label: String) raises:
    var bits = f64_to_u64(value)
    if bits != expected_bits:
        raise Error("bits mismatch for " + label)
    var back = u64_to_f64(bits)
    if f64_to_u64(back) != expected_bits:
        raise Error("roundtrip mismatch for " + label)
    print("f64", label, "bits=" + hex(bits))


def check_f32(value: Float32, expected_bits: UInt32, label: String) raises:
    var bits = f32_to_u32(value)
    if bits != expected_bits:
        raise Error("bits mismatch for " + label)
    if f32_to_u32(u32_to_f32(bits)) != expected_bits:
        raise Error("roundtrip mismatch for " + label)
    print("f32", label, "bits=" + hex(bits))


def check_int_roundtrip():
    var signed: Int64 = -9223372036854775808
    var as_unsigned = UInt64(signed.to_bits())
    var back = Int64(from_bits=as_unsigned)
    assert as_unsigned == 0x8000000000000000
    assert back == signed
    assert UInt64(Int64(-1).to_bits()) == 0xFFFFFFFFFFFFFFFF
    print("int: PASS (sign bit preserved through to_bits/from_bits)")


def main() raises:
    check_f64(0.0, 0x0000000000000000, "0.0")
    check_f64(-0.0, 0x8000000000000000, "-0.0")
    check_f64(1.0, 0x3FF0000000000000, "1.0")
    check_f64(-2.5, 0xC004000000000000, "-2.5")
    check_f64(Float64.MAX_FINITE, 0x7FEFFFFFFFFFFFFF, "max_finite")
    check_f64(u64_to_f64(0x7FF0000000000000), 0x7FF0000000000000, "inf")
    check_f64(u64_to_f64(0xFFF0000000000000), 0xFFF0000000000000, "-inf")

    var nan_value = u64_to_f64(0x7FF8000000000001)
    var nan_bits = f64_to_u64(nan_value)
    assert nan_bits & 0x7FF0000000000000 == 0x7FF0000000000000
    assert (nan_bits & 0x000FFFFFFFFFFFFF) != 0
    print("f64 nan bits=" + hex(nan_bits))

    check_f32(0.0, 0x00000000, "0.0")
    check_f32(-0.0, 0x80000000, "-0.0")
    check_f32(1.0, 0x3F800000, "1.0")
    check_f32(-2.5, 0xC0200000, "-2.5")
    check_f32(u32_to_f32(0x7F800000), 0x7F800000, "inf")

    check_int_roundtrip()
    print("float_bits: PASS")
