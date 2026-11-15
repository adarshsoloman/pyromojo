"""E17: integer division/remainder semantics and truncation helpers.

Question: Mojo's ``//`` floors (Python style) while C truncates toward zero.
The port needs an exact truncating helper for avg and ratecv.
"""


def trunc_div(numerator: Int64, denominator: Int64) -> Int64:
    """Quotient truncated toward zero, matching C integer division."""
    var quotient = numerator // denominator
    var remainder = numerator % denominator
    if remainder != 0 and ((numerator < 0) != (denominator < 0)):
        quotient += 1
    return quotient


def main() raises:
    # Mojo native semantics: floor division.
    assert -1 // 2 == -1
    assert -3 // 2 == -2
    assert 7 // 2 == 3
    assert -7 % 2 == 1

    # C semantics: truncation toward zero.
    assert trunc_div(-1, 2) == 0
    assert trunc_div(-3, 2) == -1
    assert trunc_div(-5, 2) == -2
    assert trunc_div(7, 2) == 3
    assert trunc_div(-7, 2) == -3
    assert trunc_div(5, -2) == -2
    assert trunc_div(-6, 2) == -3

    # The reference avg() truncates toward zero.
    assert trunc_div(-1, 2) == 0

    print("E17 ok: truncating division helper reproduces C semantics")
