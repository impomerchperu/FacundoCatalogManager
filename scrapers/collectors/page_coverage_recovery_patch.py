"""Recover expected Facundo JSF pages before product card extraction."""

from __future__ import annotations

from typing import Any

from .category_scraper import CategoryScraper
from .resilient_category_scraper import ResilientCategoryScraper

_PATCHED = False
_ORIGINAL_GET_CATEGORY_PAGES = CategoryScraper.get_category_pages
_ORIGINAL_RESILIENT_GET_CATEGORY_PAGES = ResilientCategoryScraper.get_category_pages


def _cached_category_html(scraper: CategoryScraper, category_url: str) -> str:
    lock = getattr(scraper, "_category_html_cache_lock", None)
    cache = getattr(scraper, "_category_html_cache", {})
    if lock is None:
        return str(cache.get(category_url, "") or "")
    with lock:
        return str(cache.get(category_url, "") or "")


def _required_page_count(category_html: str, expected_count: int) -> int:
    expected_pages = (
        (int(expected_count) + CategoryScraper.PRODUCTS_PER_PAGE - 1)
        // CategoryScraper.PRODUCTS_PER_PAGE
        if int(expected_count or 0) > 0
        else 0
    )
    visible_pages = CategoryScraper._pagination_max_page(category_html)
    return max(expected_pages, visible_pages, 1)


def _page_url(scraper: CategoryScraper, category_url: str, page: int) -> str:
    builder = getattr(scraper, "_jsf_page_url", None)
    if callable(builder):
        return str(builder(category_url, page))
    return f"{category_url.rstrip('/')}?product-page={page}"


def _recover_missing_pages(
    scraper: CategoryScraper,
    category_url: str,
    expected_count: int,
    pages: list[str],
) -> list[str]:
    if not scraper._is_facundo_url(category_url):
        return pages

    category_html = _cached_category_html(scraper, category_url)
    if not category_html:
        try:
            category_html = scraper.get_html(category_url)
        except (AttributeError, RuntimeError, TypeError, ValueError):
            return pages

    required_pages = _required_page_count(category_html, expected_count)
    if len(pages) >= required_pages:
        return pages

    category_id = scraper._category_id(category_html)
    fetcher = getattr(scraper, "_fetch_jsf_page", None)
    cache_html = getattr(scraper, "_cache_category_html", None)
    if category_id is None or not callable(fetcher) or not callable(cache_html):
        return pages

    existing_numbers = {
        CategoryScraper._page_number(url)
        for url in pages
        if CategoryScraper._page_number(url) is not None
    }
    recovered = list(pages)

    for page in range(2, required_pages + 1):
        if page in existing_numbers:
            continue
        page_url = _page_url(scraper, category_url, page)
        rendered_html = ""
        for _ in range(2):
            try:
                _, _, rendered_html = fetcher(category_url, category_id, page)
            except (RuntimeError, TypeError, ValueError):
                rendered_html = ""
            if rendered_html:
                break
        if not rendered_html:
            break
        cache_html(page_url, rendered_html)
        recovered.append(page_url)
        existing_numbers.add(page)

    return recovered


def _get_category_pages_with_recovery(
    self: CategoryScraper,
    category_url: str,
    expected_count: int = 0,
) -> list[str]:
    pages = _ORIGINAL_GET_CATEGORY_PAGES(
        self,
        category_url,
        expected_count=expected_count,
    )
    return _recover_missing_pages(self, category_url, expected_count, list(pages))


def _get_resilient_category_pages_with_recovery(
    self: ResilientCategoryScraper,
    category_url: str,
    expected_count: int = 0,
) -> list[str]:
    pages = _ORIGINAL_RESILIENT_GET_CATEGORY_PAGES(
        self,
        category_url,
        expected_count=expected_count,
    )
    return _recover_missing_pages(self, category_url, expected_count, list(pages))


def activate() -> None:
    """Install page recovery once without changing card extraction."""
    global _PATCHED
    if _PATCHED:
        return
    CategoryScraper.get_category_pages = _get_category_pages_with_recovery
    ResilientCategoryScraper.get_category_pages = (
        _get_resilient_category_pages_with_recovery
    )
    _PATCHED = True


activate()

__all__ = ["activate"]
