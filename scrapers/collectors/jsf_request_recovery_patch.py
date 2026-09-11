"""Retry transient JetSmartFilters request failures at page level."""

from __future__ import annotations

import requests

from . import category_pagination_patch as _category_pagination_patch
from .category_scraper import CategoryScraper

_PATCHED = False
_ORIGINAL_RETRY_JSF_PAGE = _category_pagination_patch._retry_jsf_page


def _retry_jsf_page(
    self: CategoryScraper,
    category_url: str,
    category_id: int,
    page: int,
):
    """Retry transport-level JSF failures before declaring a page unavailable."""
    last_error: requests.exceptions.RequestException | None = None
    for _ in range(_category_pagination_patch.JSF_PAGE_RETRIES):
        try:
            return _category_pagination_patch._fetch_jsf_page_direct(
                self,
                category_url,
                category_id,
                page,
            )
        except requests.exceptions.RequestException as error:
            last_error = error
            continue

    if last_error is not None:
        raise last_error
    return _ORIGINAL_RETRY_JSF_PAGE(self, category_url, category_id, page)


def activate() -> None:
    """Install the request-level retry layer once."""
    global _PATCHED
    if _PATCHED:
        return
    _category_pagination_patch._retry_jsf_page = _retry_jsf_page
    _PATCHED = True


activate()

__all__ = ["activate"]
