"""Compatibility facade for the canonical category pagination engine.

The implementation lives in ``category_pagination_engine``.  This module
preserves historical helper names used by legacy callers and tests.
"""

from __future__ import annotations

from . import category_pagination_engine as _engine
from .category_pagination_engine import (
    JSF_PAGE_RETRIES,
    _JSF_QUERY_STATE,
    _JSF_REQUEST_STATE,
    _JSF_STATE_LOCK,
    _browser_compatible_jsf_payload,
    _collect_direct_pages,
    _direct_product_urls,
    _remember_jsf_metadata,
    _remember_jsf_settings,
    _retry_jsf_page,
    get_category_pages as _engine_get_category_pages,
    pages_required,
)
from .category_scraper import CategoryScraper


# Historical private entry point retained for compatibility.
def get_category_pages(
    self: CategoryScraper,
    category_url: str,
    expected_count: int = 0,
) -> list[str]:
    """Delegate the historical hook to the canonical pagination engine."""
    return _engine_get_category_pages(
        self,
        category_url,
        expected_count=expected_count,
    )


_get_category_pages = get_category_pages

_PATCHED = False


def activate() -> None:
    """Install the canonical pagination callable through the legacy hook."""
    global _PATCHED
    if _PATCHED:
        return
    CategoryScraper.get_category_pages = get_category_pages
    _PATCHED = True


activate()

assert _engine.get_category_pages is _engine_get_category_pages

__all__ = [
    "JSF_PAGE_RETRIES",
    "_JSF_QUERY_STATE",
    "_JSF_REQUEST_STATE",
    "_JSF_STATE_LOCK",
    "_browser_compatible_jsf_payload",
    "_collect_direct_pages",
    "_direct_product_urls",
    "_get_category_pages",
    "_remember_jsf_metadata",
    "_remember_jsf_settings",
    "_retry_jsf_page",
    "activate",
    "get_category_pages",
    "pages_required",
]
