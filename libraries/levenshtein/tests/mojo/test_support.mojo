"""Deterministic test support: seeded LCG and random string builders."""

from std.collections import List

from mojo_levenshtein.unicode import to_codepoints


struct TestRng:
    """Minimal LCG with an explicit seed; reproducible across runs."""

    var state: UInt64

    def __init__(out self, seed: UInt64):
        self.state = seed

    def next(mut self, bound: Int) -> Int:
        self.state = (
            self.state * UInt64(6364136223846793005)
            + UInt64(1442695040888963407)
        )
        return Int(self.state % UInt64(bound))


def random_ascii(mut rng: TestRng, length: Int) raises -> String:
    var raw = List[UInt8](capacity=length)
    for _ in range(length):
        raw.append(UInt8(rng.next(26) + 97))
    return String(from_utf8=Span(raw))


def random_codepoints(mut rng: TestRng, length: Int) -> List[Int]:
    var alphabet = List[Int](capacity=8)
    alphabet.append(97)
    alphabet.append(98)
    alphabet.append(99)
    alphabet.append(233)
    alphabet.append(0x1F600)
    alphabet.append(0x4E2D)
    alphabet.append(32)
    alphabet.append(122)
    var out = List[Int](capacity=length)
    for _ in range(length):
        out.append(alphabet[rng.next(len(alphabet))])
    return out^


def ascii_string(code: Int, count: Int) raises -> String:
    var raw = List[UInt8](capacity=count)
    for _ in range(count):
        raw.append(UInt8(code))
    return String(from_utf8=Span(raw))
