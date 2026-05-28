"""Tests for the example tools.

`@tool`-decorated functions are wrapped in a Tool instance; the underlying
callable is reachable as `tool_obj.forward`.
"""

from __future__ import annotations

import math

import pytest

from lean_agent.tools import (
    ALL_TOOLS,
    caesar_cipher,
    compound_interest,
    fibonacci,
    get_current_time,
    is_palindrome,
    is_prime,
    reverse_words,
    roll_dice,
    temperature_convert,
    word_count,
)


def test_all_tools_registered():
    names = {t.name for t in ALL_TOOLS}
    assert names == {
        "get_current_time",
        "word_count",
        "fibonacci",
        "compound_interest",
        "is_prime",
        "is_palindrome",
        "temperature_convert",
        "roll_dice",
        "caesar_cipher",
        "reverse_words",
    }


# --- existing tools ---


def test_get_current_time_utc():
    result = get_current_time.forward(tz="UTC")
    assert "T" in result
    assert result.endswith("+00:00")


def test_get_current_time_unknown_tz_falls_back():
    result = get_current_time.forward(tz="Not/A_Real_Zone")
    assert result.endswith("+00:00")


def test_word_count_basic():
    assert word_count.forward(text="hello world") == 2
    assert word_count.forward(text="") == 0
    assert word_count.forward(text="   spaced   out   words ") == 3


@pytest.mark.parametrize("n,expected", [(0, 0), (1, 1), (2, 1), (10, 55), (20, 6765)])
def test_fibonacci_values(n, expected):
    assert fibonacci.forward(n=n) == expected


def test_fibonacci_negative_raises():
    with pytest.raises(ValueError):
        fibonacci.forward(n=-1)


def test_compound_interest_basic():
    expected = 1000 * (1.05) ** 10
    assert math.isclose(
        compound_interest.forward(principal=1000, annual_rate=0.05, years=10),
        expected,
    )


def test_compound_interest_zero_years_returns_principal():
    assert compound_interest.forward(principal=500.0, annual_rate=0.1, years=0) == 500.0


def test_compound_interest_negative_raises():
    with pytest.raises(ValueError):
        compound_interest.forward(principal=-1, annual_rate=0.05, years=1)


# --- new tools ---


@pytest.mark.parametrize(
    "n,expected",
    [(-5, False), (0, False), (1, False), (2, True), (3, True), (4, False),
     (17, True), (25, False), (97, True), (100, False)],
)
def test_is_prime(n, expected):
    assert is_prime.forward(n=n) is expected


@pytest.mark.parametrize(
    "text,expected",
    [
        ("racecar", True),
        ("A man, a plan, a canal: Panama", True),
        ("hello", False),
        ("", True),  # empty string is trivially a palindrome
        ("No 'x' in Nixon", True),
    ],
)
def test_is_palindrome(text, expected):
    assert is_palindrome.forward(text=text) is expected


def test_temperature_convert_known_values():
    assert math.isclose(temperature_convert.forward(value=0, from_unit="C", to_unit="F"), 32.0)
    assert math.isclose(temperature_convert.forward(value=100, from_unit="C", to_unit="K"), 373.15)
    assert math.isclose(temperature_convert.forward(value=32, from_unit="F", to_unit="C"), 0.0)
    # round-trip
    assert math.isclose(
        temperature_convert.forward(
            value=temperature_convert.forward(value=21.5, from_unit="C", to_unit="F"),
            from_unit="F",
            to_unit="C",
        ),
        21.5,
    )


def test_temperature_convert_case_insensitive():
    assert math.isclose(temperature_convert.forward(value=0, from_unit="c", to_unit="k"), 273.15)


def test_temperature_convert_invalid_unit_raises():
    with pytest.raises(ValueError):
        temperature_convert.forward(value=0, from_unit="C", to_unit="X")


def test_roll_dice_within_range():
    rolls = roll_dice.forward(num_dice=20, sides=6)
    assert len(rolls) == 20
    assert all(1 <= r <= 6 for r in rolls)


def test_roll_dice_invalid_raises():
    with pytest.raises(ValueError):
        roll_dice.forward(num_dice=0, sides=6)
    with pytest.raises(ValueError):
        roll_dice.forward(num_dice=1, sides=1)


def test_caesar_cipher_basic():
    assert caesar_cipher.forward(text="abc XYZ!", shift=3) == "def ABC!"


def test_caesar_cipher_round_trip():
    plaintext = "Hello, World!"
    cipher = caesar_cipher.forward(text=plaintext, shift=13)
    assert caesar_cipher.forward(text=cipher, shift=-13) == plaintext


def test_caesar_cipher_wraps():
    assert caesar_cipher.forward(text="xyz", shift=3) == "abc"


def test_reverse_words():
    assert reverse_words.forward(text="one two three") == "three two one"
    assert reverse_words.forward(text="hello") == "hello"
    assert reverse_words.forward(text="") == ""
