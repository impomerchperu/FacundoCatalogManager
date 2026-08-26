"""Compatibility helpers for category pagination."""


def pages_required(expected_count: int, products_per_page: int = 25) -> int:
    """Return pages required by one category's own product count."""
    count = max(int(expected_count or 0), 0)
    if count == 0:
        return 0
    return (count + products_per_page - 1) // products_per_page


__all__ = ["pages_required"]
