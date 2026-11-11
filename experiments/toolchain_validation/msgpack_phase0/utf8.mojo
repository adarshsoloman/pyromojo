"""Phase 0 probe: UTF-8 construction, validation, and byte access."""

from std.collections import List, Span


def bytes_of(var values: List[Int]) -> List[UInt8]:
    var out = List[UInt8](capacity=len(values))
    for v in values:
        out.append(UInt8(v))
    return out^


def check_valid(var values: List[Int], expected: String) raises:
    var raw = bytes_of(values^)
    var s = String(from_utf8=Span(raw))
    assert s == expected, "decoded text mismatch"
    assert s.byte_length() == len(raw)
    var view = s.as_bytes()
    assert len(view) == s.byte_length()
    for i in range(len(raw)):
        assert view[i] == raw[i]
    print("valid:", s, "bytes=", s.byte_length())


def check_invalid(var values: List[Int], label: String):
    var raw = bytes_of(values^)
    var raised = False
    try:
        var s = String(from_utf8=Span(raw))
        print(label, "UNEXPECTEDLY ACCEPTED:", s)
    except e:
        raised = True
        print(label, "rejected:", e)

    assert raised, label

    var lossy = String(from_utf8_lossy=Span(raw))
    print(label, "lossy:", lossy)
    assert lossy.byte_length() > 0


def check_unsafe_constructor():
    var raw = bytes_of([0x68, 0x69])
    var s = String(unsafe_from_utf8=Span(raw))
    assert s == "hi"
    assert s.as_bytes()[1] == 0x69
    print("unsafe_from_utf8: PASS")


def check_embedded_nul() raises:
    var raw = bytes_of([0x61, 0x00, 0x62])
    var s = String(from_utf8=Span(raw))
    assert s.byte_length() == 3
    assert s.as_bytes()[1] == 0
    print("embedded NUL: PASS (byte_length 3)")


def main() raises:
    check_valid([0x41], "A")
    check_valid([0xC3, 0xA9], "é")
    check_valid([0xE2, 0x82, 0xAC], "€")
    check_valid([0xF0, 0x9F, 0x98, 0x80], "😀")
    check_valid([0x00], "\0")

    check_invalid([0x80], "lone continuation")
    check_invalid([0xC0, 0x80], "overlong NUL")
    check_invalid([0xE2, 0x82], "truncated 3-byte")
    check_invalid([0xED, 0xA0, 0x80], "UTF-16 surrogate")
    check_invalid([0xF4, 0x90, 0x80, 0x80], "above U+10FFFF")

    check_unsafe_constructor()
    check_embedded_nul()
    print("utf8: PASS")
