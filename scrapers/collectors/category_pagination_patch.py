"""Reliable pagination compatibility layer for Facundo category archives."""

from __future__ import annotations

import re
from urllib.parse import urljoin

from .category_scraper import CategoryScraper

_PATCHED = False
_ORIGINAL_GET_CATEGORY_PAGES = CategoryScraper.get_category_pages
_ORIGINAL_FETCH_JSF_PAGE = CategoryScraper._fetch_jsf_page
_PRODUCT_URL_PATTERN = re.compile(
    r'href=["\']([^"\']*/producto/[^"\'#?]+/?)[^"\']*["\']',
    re.IGNORECASE,
)
JSF_PAGE_RETRIES = 3


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


def _remember_jsf_page_limit(
    self: CategoryScraper,
    category_url: str,
    first_html: str,
    expected_count: int,
) -> None:
    """Remember pages required by coverage before trusting JSF metadata."""
    expected_pages = self._required_page_count(max(int(expected_count or 0), 0))
    declared_total_pages = self._declared_total_pages(first_html)
    declared_pagination_max_page = self._pagination_max_page(first_html)
    configured_limit = max(
        expected_pages,
        declared_total_pages,
        declared_pagination_max_page,
    )

    cache_lock = getattr(self, "_jsf_cache_lock", None)
    page_limits = getattr(self, "_jsf_page_limits", None)
    if page_limits is None:
        page_limits = {}
        self._jsf_page_limits = page_limits

    if cache_lock is not None:
        with cache_lock:
            page_limits[category_url] = configured_limit
    else:
        page_limits[category_url] = configured_limit


def _retry_jsf_page(
    self: CategoryScraper,
    category_url: str,
    category_id: int,
    page: int,
):
    """Retry transient empty/failed JSF pages before pagination gives up."""
    cache_lock = getattr(self, "_jsf_cache_lock", None)
    metadata_cache = getattr(self, "_jsf_metadata_cache", None)
    page_limits = getattr(self, "_jsf_page_limits", {})

    if cache_lock is not None and metadata_cache is not None:
        with cache_lock:
            cached_metadata = metadata_cache.get(category_url)
    elif metadata_cache is not None:
        cached_metadata = metadata_cache.get(category_url)
    else:
        cached_metadata = None

    configured_limit = page_limits.get(category_url, 0)
    if cached_metadata is not None:
        found_posts, declared_max_num_pages = cached_metadata
        published_pages = self._required_page_count(found_posts)
        last_expected_page = max(
            declared_max_num_pages,
            published_pages,
            configured_limit,
        )
        if last_expected_page > 0 and page > last_expected_page:
            return _ORIGINAL_FETCH_JSF_PAGE(
                self,
                category_url,
                category_id,
                page,
            )

    last_error: Exception | None = None
    result = (0, 0, "")
    for _ in range(JSF_PAGE_RETRIES):
        try:
            result = _ORIGINAL_FETCH_JSF_PAGE(
                self,
                category_url,
                category_id,
                page,
            )
        except (RuntimeError, TypeError, ValueError) as error:
            last_error = error
            continue
        if result[2]:
            return result
    if last_error is not None:
        raise last_error
    return result


def _facundo_jsf_pages(
    scraper: CategoryScraper,
    category_url: str,
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
    """Use JSF as the authoritative Facundo pagination path."""
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
        _remember_jsf_page_limit(
            self,
            category_url,
            first_html,
            expected_count,
        )
        self._cache_category_html(category_url, first_html)
        return _facundo_jsf_pages(
            self,
            category_url,
            expected_count,
        )

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
    return _ORIGINAL_GET_CATEGORY_PAGES(
        self,
        category_url,
        expected_count=expected_count,
    )


def activate() -> None:
    """Install the compatibility behavior once for the collectors package."""
    global _PATCHED
    if not _PATCHED:
        CategoryScraper._original_get_category_pages = _ORIGINAL_GET_CATEGORY_PAGES
        CategoryScraper._original_fetch_jsf_page = _ORIGINAL_FETCH_JSF_PAGE
        CategoryScraper._fetch_jsf_page = _retry_jsf_page
        CategoryScraper.get_category_pages = _get_category_pages
        _PATCHED = True


activate()

__all__ = ["JSF_PAGE_RETRIES", "CategoryScraper", "activate", "pages_required"]
