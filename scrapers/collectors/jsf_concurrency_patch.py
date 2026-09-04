"""Limit concurrent JetSmartFilters AJAX requests to avoid server-side 500s."""

from __future__ import annotations

from threading import BoundedSemaphore

from scrapers.collectors.category_scraper import CategoryScraper
# The live JetSmartFilters endpoint has returned HTTP 500 when many category
# workers hit admin-ajax.php simultaneously. Keep category workers unchanged
# and throttle only this fragile endpoint so detail HTTP concurrency is intact.
JSF_HTTP_CONCURRENCY = 4

_SEMAPHORE = BoundedSemaphore(JSF_HTTP_CONCURRENCY)
_ORIGINAL_POST_JSF = CategoryScraper._post_jsf
_PATCHED = False


def _post_jsf(self, payload):
    with _SEMAPHORE:
        return _ORIGINAL_POST_JSF(self, payload)


def activate() -> None:
    """Install the JetSmartFilters concurrency guard once."""
    global _PATCHED
    if _PATCHED:
        return
    CategoryScraper._post_jsf = _post_jsf
    _PATCHED = True


activate()

__all__ = ["JSF_HTTP_CONCURRENCY", "activate"]
