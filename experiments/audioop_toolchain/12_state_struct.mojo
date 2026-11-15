"""E12: mutable codec state across calls.

Question: can adpcm/ratecv state (predictor, index, previous samples) live in
a struct that mutates across calls, matching the reference's state tuples?
"""


struct RatecvState(RegisterPassable, ImplicitlyCopyable):
    var previous: Int32
    var accumulated: Int64
    var count: Int64

    def __init__(out self, previous: Int32, accumulated: Int64, count: Int64):
        self.previous = previous
        self.accumulated = accumulated
        self.count = count


    def feed(mut self, sample: Int32) -> Int32:
        self.accumulated += Int64(sample - self.previous)
        self.count += 1
        self.previous = sample
        return Int32(self.accumulated // self.count)


struct AdpcmState(RegisterPassable, ImplicitlyCopyable):
    var predicted: Int32
    var index: Int32

    def __init__(out self, predicted: Int32, index: Int32):
        self.predicted = predicted
        self.index = index


    def update(mut self, delta: Int32) -> Int32:
        self.predicted += delta
        self.index = (self.index + 1) % 89
        return self.predicted


def main() raises:
    var rate = RatecvState(0, 0, 0)
    var first = rate.feed(100)
    assert first == 100
    var second = rate.feed(0)
    assert second == 50
    assert rate.previous == 0 and rate.count == 2

    var adpcm = AdpcmState(0, 0)
    assert adpcm.update(16) == 16
    assert adpcm.index == 1
    assert adpcm.update(-4) == 12
    assert adpcm.predicted == 12

    # Structs are value types: a copy does not share state.
    var saved = adpcm
    _ = saved.update(1000)
    assert adpcm.predicted == 12
    assert saved.predicted == 1012

    print("E12 ok: mutable struct state, value-copy isolation")
