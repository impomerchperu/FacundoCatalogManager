"""Reliable pagination compatibility layer for Facundo category archives."""

from __future__ import annotations

import re
from urllib.parse import urljoin

from .category_scraper import CategoryScraper

_PATCHED = False
_ORIGINAL_GET_CATEGORY_PAGES = CategoryScraper.get_category_pages
_PRODUCT_URL_PATTERN = re.compile(
    r'href=["\']([^"\']*/producto/[^"\'#?]+/?)[^"\']*["\']',
    re.IGNORECASE,
)


def pages_required(expected_count: int, products_per_page: int = 25) -> int:
    """Return a coverage estimate; it is never a hard pagination ceiling."""
    count = max(int(expected_count or 0), 0)
    per_page = max(int(products_per_page or 25), 1)
    return 0 if count == 0 else (count + per_page - 1) // per_page


def _safe_get_html(scraper: CategoryScraper, url: str) -> str:
    try:
        return scraper.get_html(url)
    except (AttributeError, RuntimeError, TypeError, ValueError):
        return ""


def _direct_product_urls(html: str, base_url: str) -> set[str]:
    urls: set[str] = set()
    for raw_url in _PRODUCT_URL_PATTERN.findall(html or ""):
        absolute = urljoin(base_url.rstrip("/") + "/", raw_url)
        normalized = absolute.rstrip("/")
        if "/producto/" in normalized.casefold():
            urls.add(normalized)
    return urls


def _facundo_direct_pages(
    scraper: CategoryScraper,
    category_url: str,
    first_html: str,
    expected_count: int,
) -> tuple[list[str], int]:
    """Collect public archive pages as a compatibility fallback."""
    pages = scraper._fallback_category_pages(
        category_url,
        first_html,
        expected_count,
    )
    product_urls: set[str] = set(_direct_product_urls(first_html, category_url))

    for page_url in pages[1:]:
        html = scraper._category_html_cache.get(page_url, "")
        if html:
            product_urls.update(_direct_product_urls(html, page_url))

    return pages, len(product_urls)


def _facundo_jsf_pages(
    scraper: CategoryScraper,
    category_url: str,
    category_id: int,
    expected_count: int,
) -> list[str]:
    """Use CategoryScraper's JSF pagination semantics for Facundo archives."""
    return scraper._original_get_category_pages(
        category_url,
        expected_count=expected_count,
    )


def _get_category_pages(
    self: CategoryScraper,
    category_url: str,
    expected_count: int = 0,
) -> list[str]:
    """Prefer JSF pagination for Facundo and retain public pagination as fallback."""
    first_html = _safe_get_html(self, category_url)
    if not first_html:
        return []

    if not self._is_facundo_url(category_url):
        self._cache_category_html(category_url, first_html)
        return _ORIGINAL_GET_CATEGORY_PAGES(
            self,
            category_url,
            expected_count=expected_count,
        )

    category_id = self._category_id(first_html)
    if category_id is not None:
        try:
            jsf_pages = _facundo_jsf_pages(
                self,
                category_url,
                category_id,
                expected_count,
            )
            required_pages = pages_required(expected_count)
            if required_pages == 0 or len(jsf_pages) >= required_pages:
                self._cache_category_html(category_url, first_html)
                return jsf_pages
        except (RuntimeError, TypeError, ValueError):
            pass

    direct_products = _direct_product_urls(first_html, category_url)
    if direct_products:
        direct_pages, direct_count = _facundo_direct_pages(
            self,
            category_url,
            first_html,
            expected_count,
        )
        expected = max(int(expected_count or 0), 0)
        if expected == 0 or direct_count >= expected:
            self._cache_category_html(category_url, first_html)
            return direct_pages

    self._cache_category_html(category_url, first_html)
    if category_id is None:
        return _ORIGINAL_GET_CATEGORY_PAGES(
            self,
            category_url,
            expected_count=expected_count,
        )

    return _facundo_jsf_pages(
        self,
        category_url,
        category_id,
        expected_count,
    )


def activate() -> None:
    """Install the compatibility behavior once for the collectors package."""
    global _PATCHED
    if not _PATCHED:
        CategoryScraper._original_get_category_pages = _ORIGINAL_GET_CATEGORY_PAGES
        CategoryScraper.get_category_pages = _get_category_pages
        _PATCHED = True


activate()

__all__ = ["CategoryScraper", "activate", "pages_required"]
