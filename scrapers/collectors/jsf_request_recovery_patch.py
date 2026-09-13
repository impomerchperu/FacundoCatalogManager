"""Compatibility facade for canonical JetSmartFilters request recovery."""

from __future__ import annotations

from .category_pagination_engine import JSF_PAGE_RETRIES

_PATCHED = True


def activate() -> None:
    """Keep the historical activation hook without monkey-patching runtime code."""
    return None


__all__ = ["JSF_PAGE_RETRIES", "activate"]
