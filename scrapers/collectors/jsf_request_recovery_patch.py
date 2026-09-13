"""Compatibility facade for canonical JetSmartFilters request recovery."""

from __future__ import annotations

from .category_pagination_engine import JSF_PAGE_RETRIES, _retry_jsf_page

_PATCHED = True

# Historical helper retained as an alias to the canonical implementation.
_retry_jsf_page = _retry_jsf_page


def activate() -> None:
    """Keep the historical activation hook without monkey-patching runtime code."""
    return None


__all__ = ["JSF_PAGE_RETRIES", "_retry_jsf_page", "activate"]
