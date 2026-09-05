"""Recover first JetSmartFilters page through the original fetch path."""

from __future__ import annotations

from . import category_pagination_patch
from .category_scraper import CategoryScraper

JSF_PAGE_RETRIES = category_pagination_patch.JSF_PAGE_RETRIES
_ORIGINAL_FETCH_JSF_PAGE = category_pagination_patch._ORIGINAL_FETCH_JSF_PAGE


def _retry_first_page(
    self: CategoryScraper,
    category_url: str,
    category_id: int,
    page: int,
):
    """Retry the original JSF fetch without adding another wrapper layer."""
    fetcher = _ORIGINAL_FETCH_JSF_PAGE.__get__(self, CategoryScraper)
    last_error: Exception | None = None
    result = (0, 0, "")
    for _ in range(JSF_PAGE_RETRIES):
        try:
            result = fetcher(category_url, category_id, page)
        except (RuntimeError, TypeError, ValueError) as error:
            last_error = error
            continue
        if result[2] or result[0] > 0 or result[1] > 0:
            return result
    if last_error is not None:
        raise last_error
    return result


# The pagination patch calls this module-level helper by global name, so replace
# that helper while keeping every other pagination behavior untouched.
category_pagination_patch._retry_jsf_page = _retry_first_page
CategoryScraper._fetch_jsf_page = _retry_first_page

__all__ = ["JSF_PAGE_RETRIES", "_retry_first_page"]
