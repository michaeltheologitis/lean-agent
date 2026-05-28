"""Example tools for the lean agent.

Each tool follows the smolagents contract:
- type hints on every argument and on the return value
- a docstring with a one-line summary and an `Args:` section describing
  every parameter (smolagents parses this to build the tool schema)
"""

from __future__ import annotations

import random
from datetime import datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from smolagents import tool


@tool
def get_current_time(tz: str = "UTC") -> str:
    """Return the current wall-clock time in the given IANA timezone.

    Args:
        tz: An IANA timezone name such as "UTC", "Europe/Athens",
            "America/New_York". Defaults to "UTC".
    """
    try:
        zone = ZoneInfo(tz)
    except ZoneInfoNotFoundError:
        zone = timezone.utc
    return datetime.now(zone).isoformat(timespec="seconds")


@tool
def word_count(text: str) -> int:
    """Count whitespace-separated words in a string.

    Args:
        text: The input string to tokenize and count.
    """
    return len(text.split())


@tool
def fibonacci(n: int) -> int:
    """Compute the n-th Fibonacci number (0-indexed, F(0)=0, F(1)=1).

    Args:
        n: Non-negative index of the Fibonacci sequence to compute.
    """
    if n < 0:
        raise ValueError("n must be non-negative")
    a, b = 0, 1
    for _ in range(n):
        a, b = b, a + b
    return a


@tool
def compound_interest(principal: float, annual_rate: float, years: float) -> float:
    """Compute the future value of a principal under annual compounding.

    Args:
        principal: The starting amount of money.
        annual_rate: The annual interest rate expressed as a decimal
            (e.g. 0.05 for 5%).
        years: The number of years the money is invested for. Fractional
            years are allowed.
    """
    if principal < 0 or years < 0:
        raise ValueError("principal and years must be non-negative")
    return principal * (1 + annual_rate) ** years


@tool
def is_prime(n: int) -> bool:
    """Check whether an integer is prime.

    Args:
        n: The integer to test. Negatives, 0 and 1 are not prime.
    """
    if n < 2:
        return False
    if n < 4:
        return True
    if n % 2 == 0:
        return False
    i = 3
    while i * i <= n:
        if n % i == 0:
            return False
        i += 2
    return True


@tool
def is_palindrome(text: str) -> bool:
    """Check whether a string reads the same forwards and backwards,
    ignoring case and non-alphanumeric characters.

    Args:
        text: The string to test.
    """
    cleaned = [c.lower() for c in text if c.isalnum()]
    return cleaned == cleaned[::-1]


@tool
def temperature_convert(value: float, from_unit: str, to_unit: str) -> float:
    """Convert a temperature between Celsius (C), Fahrenheit (F), and Kelvin (K).

    Args:
        value: The temperature value to convert.
        from_unit: The unit of `value`. One of "C", "F", "K" (case-insensitive).
        to_unit: The target unit. One of "C", "F", "K" (case-insensitive).
    """
    src, dst = from_unit.upper(), to_unit.upper()
    if src not in {"C", "F", "K"} or dst not in {"C", "F", "K"}:
        raise ValueError("units must be one of C, F, K")
    # First normalize to Celsius.
    if src == "F":
        celsius = (value - 32) * 5 / 9
    elif src == "K":
        celsius = value - 273.15
    else:
        celsius = value
    # Then convert to target.
    if dst == "F":
        return celsius * 9 / 5 + 32
    if dst == "K":
        return celsius + 273.15
    return celsius


@tool
def roll_dice(num_dice: int, sides: int = 6) -> list[int]:
    """Roll one or more dice and return the individual results.

    Args:
        num_dice: How many dice to roll. Must be at least 1.
        sides: Number of sides per die. Defaults to 6. Must be at least 2.
    """
    if num_dice < 1:
        raise ValueError("num_dice must be at least 1")
    if sides < 2:
        raise ValueError("sides must be at least 2")
    return [random.randint(1, sides) for _ in range(num_dice)]


@tool
def caesar_cipher(text: str, shift: int) -> str:
    """Encrypt text with a Caesar cipher (letters shifted by `shift`,
    non-letters preserved). A negative shift decrypts.

    Args:
        text: The plaintext (or ciphertext, with negative shift) to transform.
        shift: How many letter positions to rotate by. Wraps around the alphabet.
    """
    out = []
    for ch in text:
        if "a" <= ch <= "z":
            out.append(chr((ord(ch) - ord("a") + shift) % 26 + ord("a")))
        elif "A" <= ch <= "Z":
            out.append(chr((ord(ch) - ord("A") + shift) % 26 + ord("A")))
        else:
            out.append(ch)
    return "".join(out)


@tool
def reverse_words(text: str) -> str:
    """Reverse the order of whitespace-separated words in a string.

    Args:
        text: The string whose words should be reversed.
    """
    return " ".join(text.split()[::-1])


ALL_TOOLS = [
    get_current_time,
    word_count,
    fibonacci,
    compound_interest,
    is_prime,
    is_palindrome,
    temperature_convert,
    roll_dice,
    caesar_cipher,
    reverse_words,
]
