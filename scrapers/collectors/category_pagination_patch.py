"""Compatibility facade for the canonical category pagination engine.

The pagination implementation lives in ``category_pagination_engine``.
This module only installs the canonical callable for legacy import paths.
"""

from __future__ import annotations

from .category_pagination_engine import (
    JSF_PAGE_RETRIES,
    get_category_pages as _canonical_get_category_pages,
    pages_required,
)
from .category_scraper import CategoryScraper

_PATCHED = False


def get_category_pages(
    self: CategoryScraper,
    category_url: str,
    expected_count: int = 0,
) -> list[str]:
    """Delegate the historical hook to the canonical pagination engine."""
    return _canonical_get_category_pages(
        self,
        category_url,
        expected_count=expected_count,
    )


def activate() -> None:
    """Install the canonical engine through the historical hook."""
    global _PATCHED
    if _PATCHED:
        return
    CategoryScraper.get_category_pages = get_category_pages
    _PATCHED = True


activate()

__all__ = ["JSF_PAGE_RETRIES", "activate", "get_category_pages", "pages_required"]
