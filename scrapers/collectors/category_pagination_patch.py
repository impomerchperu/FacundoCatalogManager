"""Reliable pagination compatibility layer for Facundo category archives."""

from __future__ import annotations

import re

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


def _product_keys(html: str) -> set[str]:
    keys = CategoryScraper._product_keys(html)
    if keys:
        return keys
    return set(_PRODUCT_URL_PATTERN.findall(html or ""))


def _facundo_jsf_pages(
    scraper: CategoryScraper,
    category_url: str,
    category_id: int,
    first_html: str,
    expected_count: int,
) -> list[str]:
    """Discover all JSF pages, expanding beyond incomplete metadata when needed."""
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
    seen = _product_keys(rendered_first)
    previous_html = rendered_first
    page = 2
    hidden_probes = 0

    while True:
        # First exhaust every page indicated by metadata or expected coverage.
        within_known_range = page <= metadata_pages
        # Then probe consecutive pages, but only while a new product-bearing page
        # is actually returned. This handles underreported JSF metadata without
        # making expected_count a hard ceiling.
        if not within_known_range:
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
        current = _product_keys(rendered_html)

        if not rendered_html or rendered_html == previous_html:
            break
        # JSF can return a different wrapper around the same result set. Product
        # identity, rather than raw HTML equality, is the terminal condition.
        if current and not current - seen:
            break
        if not current:
            break

        seen.update(current)
        scraper._cache_category_html(page_url, rendered_html)
        pages.append(page_url)
        previous_html = rendered_html
        page += 1

    return pages


def _get_category_pages(
    self: CategoryScraper, category_url: str, expected_count: int = 0
) -> list[str]:
    """Discover every Facundo archive page before product extraction begins."""
    first_html = _safe_get_html(self, category_url)
    if not first_html:
        return []

    category_id = self._category_id(first_html)
    if category_id is not None and self._is_facundo_url(category_url):
        return _facundo_jsf_pages(
            self,
            category_url,
            category_id,
            first_html,
            expected_count,
        )

    self._cache_category_html(category_url, first_html)
    return _ORIGINAL_GET_CATEGORY_PAGES(
        self, category_url, expected_count=expected_count
    )


def activate() -> None:
    """Install the compatibility behavior once for the collectors package."""
    global _PATCHED
    if not _PATCHED:
        CategoryScraper.get_category_pages = _get_category_pages
        _PATCHED = True


activate()

__all__ = ["CategoryScraper", "activate", "pages_required"]
