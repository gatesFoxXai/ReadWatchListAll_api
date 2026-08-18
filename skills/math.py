"""math.py - Math operations skill module.

Provides basic arithmetic functions that can be used by other parts of the project or
exposed as a skill for Copilot.
"""


def add(a: float, b: float) -> float:
    """Return the sum of a and b."""
    return a + b


def subtract(a: float, __b: float) -> float:
    """Return the difference a - b."""
    return a - __b


def multiply(a: float, b: float) -> float:
    """Return the product of a and b."""
    return a * b


def divide(a: float, b: float) -> float:
    """Return a / b, raising ZeroDivisionError if b is zero."""
    if b == 0:
        raise ValueError("Division by " "zero is not allowed")
    return a / b
