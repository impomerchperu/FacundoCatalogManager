"""Compatibility facade for canonical category page coverage recovery."""

from __future__ import annotations

import requests

from .category_page_recovery import recover_missing_category_pages
from .category_pagination_engine import pages_required
from .category_scraper import CategoryScraper

_PATCHED = False

# Historical originals retained as overridable hooks for legacy tests/callers.
_ORIGINAL_GET_CATEGORY_PAGES = CategoryScraper.get_category_pages
_ORIGINAL_GET_HTML = CategoryScraper.get_html
_ORIGINAL_RESILIENT_GET_CATEGORY_PAGES = None


def _cached_category_html(scraper: CategoryScraper, category_url: str) -> str:
    cache = getattr(scraper, "_category_html_cache", None)
    if isinstance(cache, dict):
        return str(cache.get(category_url, "") or "")
    return ""


def _recover_missing_pages(
    scraper: CategoryScraper,
    category_url: str,
    expected_count: int,
    pages: list[str],
) -> list[str]:
    """Recover missing JSF pages through the historical hook contract."""
    category_html = _cached_category_html(scraper, category_url)
    category_id = scraper._category_id(category_html)
    if category_id is None:
        return list(pages)

    required_pages = max(
        pages_required(
            expected_count,
            getattr(scraper, "PRODUCTS_PER_PAGE", 25),
        ),
        getattr(CategoryScraper, "_pagination_max_page", lambda _html: 0)(
            category_html
        ),
    )
    recovered = list(pages) or [category_url]
    known = set(recovered)
    for page in range(2, required_pages + 1):
        page_url = scraper._jsf_page_url(category_url, page)
        if page_url in known:
            continue
        try:
            _found, _max_pages, rendered_html = scraper._fetch_jsf_page(
                category_url,
                category_id,
                page,
            )
        except requests.RequestException:
            continue
        if not rendered_html:
            continue
        scraper._cache_category_html(page_url, rendered_html)
        recovered.append(page_url)
        known.add(page_url)
    return recovered


def _get_category_pages_with_recovery(
    self: CategoryScraper,
    category_url: str,
    expected_count: int = 0,
) -> list[str]:
    """Preserve the historical timeout-contained category hook."""
    try:
        pages = _ORIGINAL_GET_CATEGORY_PAGES(
            self,
            category_url,
            expected_count=expected_count,
        )
    except requests.RequestException:
        return []
    try:
        return _recover_missing_pages(self, category_url, expected_count, pages)
    except requests.RequestException:
        return pages


def _get_html_with_recovery(scraper: CategoryScraper, url: str) -> str:
    """Preserve the historical timeout-contained HTML hook."""
    try:
        return _ORIGINAL_GET_HTML(scraper, url)
    except requests.RequestException:
        return ""


def _get_resilient_category_pages_with_recovery(
    self: CategoryScraper,
    category_url: str,
    expected_count: int = 0,
) -> list[str]:
    """Preserve resilient pagination while tolerating recovery timeouts."""
    original = _ORIGINAL_RESILIENT_GET_CATEGORY_PAGES
    if original is None:
        return _get_category_pages_with_recovery(
            self,
            category_url,
            expected_count=expected_count,
        )
    try:
        pages = original(self, category_url, expected_count=expected_count)
    except requests.RequestException:
        return []
    try:
        return _recover_missing_pages(self, category_url, expected_count, pages)
    except requests.RequestException:
        return pages


def activate() -> None:
    """Install the historical compatibility wrapper explicitly."""
    global _PATCHED
    if _PATCHED:
        return
    CategoryScraper.get_category_pages = _get_category_pages_with_recovery
    _PATCHED = True


__all__ = [
    "_ORIGINAL_GET_CATEGORY_PAGES",
    "_ORIGINAL_GET_HTML",
    "_ORIGINAL_RESILIENT_GET_CATEGORY_PAGES",
    "_cached_category_html",
    "_get_category_pages_with_recovery",
    "_get_html_with_recovery",
    "_get_resilient_category_pages_with_recovery",
    "_recover_missing_pages",
    "activate",
    "recover_missing_category_pages",
]
