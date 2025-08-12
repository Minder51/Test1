from typing import Any

__all__ = ["add_values"]


def add_values(left: Any, right: Any) -> Any:
    """
    Return the sum of two values using the + operator.

    This works for numbers (ints, floats, Decimals) and any types that
    implement addition (e.g., strings for concatenation).

    Parameters:
        left: The first addend.
        right: The second addend.

    Returns:
        The result of left + right.

    Raises:
        TypeError: If the provided values cannot be added together.
    """
    return left + right