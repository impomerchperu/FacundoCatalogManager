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
    """Use the public archive only when it actually exposes product links."""
    pages = scraper._fallback_category_pages(
        category_url,
        first_html,
        expected_count,
    )
    product_urls: set[str] = _direct_product_urls(first_html, category_url)

    for page_url in pages:
        html = scraper._category_html_cache.get(page_url, "")
        if html:
            product_urls.update(_direct_product_urls(html, page_url))

    return pages, len(product_urls)


def _facundo_jsf_pages(
    scraper: CategoryScraper,
    category_url: str,
    category_id: int,
    first_html: str,
    expected_count: int,
) -> list[str]:
    """Use JSF as recovery when the public archive does not expose products."""
    pages = [category_url]
    scraper._cache_category_html(category_url, first_html)

    try:
        found_posts, declared_pages, rendered_first = scraper._fetch_jsf_page(
            category_url, category_id, 1
        )
    except (KeyError, RuntimeError, TypeError, ValueError):
        found_posts, declared_pages, rendered_first = 0, 0, ""

    if rendered_first:
        scraper._cache_category_html(category_url, rendered_first)

    expected_pages = max(
        pages_required(expected_count), pages_required(found_posts), 1
    )
    metadata_pages = max(int(declared_pages or 0), expected_pages)
    seen_urls = _direct_product_urls(rendered_first, category_url)
    seen_keys = scraper._product_keys(rendered_first)
    previous_html = rendered_first
    page = 2
    hidden_probes = 0

    while True:
        if page > metadata_pages:
            if hidden_probes >= scraper.MAX_HIDDEN_PAGE_PROBES:
                break
            hidden_probes += 1

        page_url = scraper._jsf_page_url(category_url, page)
        try:
            _, page_count, rendered_html = scraper._fetch_jsf_page(
                category_url, category_id, page
            )
        except (KeyError, RuntimeError, TypeError, ValueError):
            break

        metadata_pages = max(metadata_pages, int(page_count or 0))
        if not rendered_html or rendered_html == previous_html:
            break

        current_urls = _direct_product_urls(rendered_html, page_url)
        current_keys = scraper._product_keys(rendered_html)
        if current_urls and seen_urls and not current_urls - seen_urls:
            break
        if current_keys and seen_keys and not current_keys - seen_keys:
            break
        if not current_urls and not current_keys:
            break

        seen_urls.update(current_urls)
        seen_keys.update(current_keys)
        scraper._cache_category_html(page_url, rendered_html)
        pages.append(page_url)
        previous_html = rendered_html
        page += 1

    return pages


def _get_category_pages(
    self: CategoryScraper,
    category_url: str,
    expected_count: int = 0,
) -> list[str]:
    """Prefer the public archive when it contains products; otherwise use JSF."""
    first_html = _safe_get_html(self, category_url)
    if not first_html:
        return []

    if self._is_facundo_url(category_url):
        direct_product_urls = _direct_product_urls(first_html, category_url)
        if direct_product_urls:
            direct_pages, direct_count = _facundo_direct_pages(
                self,
                category_url,
                first_html,
                expected_count,
            )
            expected = max(int(expected_count or 0), 0)
            direct_complete = expected == 0 or direct_count >= expected
            if len(direct_pages) > 1 or direct_complete:
                self._cache_category_html(category_url, first_html)
                return direct_pages

        category_id = self._category_id(first_html)
        if category_id is not None:
            return _facundo_jsf_pages(
                self,
                category_url,
                category_id,
                first_html,
                expected_count,
            )

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
        CategoryScraper.get_category_pages = _get_category_pages
        _PATCHED = True


activate()

__all__ = ["CategoryScraper", "activate", "pages_required"]
