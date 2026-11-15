"""E16: raising and catching the module's error type.

Question: can the port raise a single documented error with message
validation, and can callers distinguish it from programmer panics?
"""


def require_whole_frames(fragment_length: Int, width: Int) raises:
    if width != 1 and width != 2 and width != 3 and width != 4:
        raise Error("Size should be 1, 2, 3 or 4")
    if fragment_length % width != 0:
        raise Error("not a whole number of frames")


def find_max(fragment_length: Int, search_length: Int) raises -> Int:
    if fragment_length > search_length:
        raise Error("Input sample should be longer")
    return 0


def main() raises:
    var caught = 0
    try:
        require_whole_frames(5, 3)
    except error:
        caught += 1
        assert String(error) == "not a whole number of frames"

    try:
        require_whole_frames(0, 5)
    except error:
        caught += 1
        assert String(error) == "Size should be 1, 2, 3 or 4"

    try:
        _ = find_max(10, 4)
    except error:
        caught += 1
        assert String(error) == "Input sample should be longer"

    assert caught == 3

    # A valid call does not raise.
    require_whole_frames(9, 3)
    assert find_max(4, 4) == 0

    print("E16 ok: Error raises, message text, and catch all verified")
