"""Retry transient JetSmartFilters request failures at page level."""

from __future__ import annotations

import requests

from .category_pagination_engine import (
    JSF_PAGE_RETRIES,
    _fetch_jsf_page_direct,
)
from .category_scraper import CategoryScraper

_PATCHED = False


def _retry_jsf_page(
    self: CategoryScraper,
    category_url: str,
    category_id: int,
    page: int,
):
    """Retry transport and empty-content JSF failures before giving up."""
    last_error: requests.exceptions.RequestException | None = None
    last_result = (0, 0, "")
    for _ in range(JSF_PAGE_RETRIES):
        try:
            result = _fetch_jsf_page_direct(
                self,
                category_url,
                category_id,
                page,
            )
        except requests.exceptions.RequestException as error:
            last_error = error
            continue

        last_result = result
        if result[2]:
            return result

    if last_error is not None and not last_result[2]:
        raise last_error
    return last_result


def activate() -> None:
    """Install the request-level retry layer once."""
    global _PATCHED
    if _PATCHED:
        return
    CategoryScraper._retry_jsf_page = _retry_jsf_page
    _PATCHED = True


activate()

__all__ = ["activate"]
