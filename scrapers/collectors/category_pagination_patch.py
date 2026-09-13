"""Compatibility facade for the canonical category pagination engine.

The pagination implementation lives in ``category_pagination_engine``.
This module only installs the canonical callable for legacy import paths.
"""

from __future__ import annotations

from .category_pagination_engine import (
    JSF_PAGE_RETRIES,
    _collect_direct_pages,
    _direct_product_urls,
    _jsf_category_pages_with_probe,
    _page_product_keys,
    get_category_pages,
    pages_required,
)
from .category_scraper import CategoryScraper

_PATCHED = False


def activate() -> None:
    """Install the canonical engine through the historical hook."""
    global _PATCHED
    if _PATCHED:
        return
    CategoryScraper.get_category_pages = get_category_pages
    _PATCHED = True


activate()

__all__ = ["JSF_PAGE_RETRIES", "activate", "pages_required"]