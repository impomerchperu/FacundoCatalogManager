"""Compatibility facade for the native JetSmartFilters concurrency guard.

The concurrency limit now lives in ``CategoryScraper._post_jsf``.  This module
preserves the historical constant and activation API for legacy callers and
tests without modifying ``CategoryScraper`` at import time.
"""

from __future__ import annotations

from scrapers.collectors.category_scraper import CategoryScraper

JSF_HTTP_CONCURRENCY = CategoryScraper.JSF_HTTP_CONCURRENCY
_PATCHED = False


def activate() -> None:
    """Preserve the historical activation API without monkey-patching runtime code."""
    return None


assert JSF_HTTP_CONCURRENCY == 4

__all__ = ["JSF_HTTP_CONCURRENCY", "activate"]
