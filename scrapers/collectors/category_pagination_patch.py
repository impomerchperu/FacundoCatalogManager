"""Reliable pagination compatibility layer for category archives."""

import re
from urllib.parse import urlsplit, urlunsplit

from .category_scraper import CategoryScraper

_PATCHED = False
_ORIGINAL_GET_CATEGORY_PAGES = CategoryScraper.get_category_pages
_PRODUCTS_IN_ARCHIVE_PATTERN = re.compile(
    r"Productos\s+en\s+Stock\s*[:\-]?\s*([\d\s.,]+)", re.IGNORECASE
)
_PRODUCT_URL_PATTERN = re.compile(
    r'href=["\']([^"\']*/producto/[^"\'#?]+/?)[^"\']*["\']', re.IGNORECASE
)


def pages_required(expected_count: int, products_per_page: int = 25) -> int:
    """Return only a coverage estimate; never use it as a pagination ceiling."""
    count = max(int(expected_count or 0), 0)
    per_page = max(int(products_per_page or 25), 1)
    return 0 if count == 0 else (count + per_page - 1) // per_page


def _published_product_count(html: str) -> int:
    match = _PRODUCTS_IN_ARCHIVE_PATTERN.search(html or "")
    if not match:
        return 0
    try:
        return int(re.sub(r"\D", "", match.group(1)))
    except (TypeError, ValueError):
        return 0


def _safe_get_html(scraper: CategoryScraper, url: str) -> str:
    try:
        return scraper.get_html(url)
    except (AttributeError, RuntimeError, TypeError, ValueError):
        return ""


def _product_keys(scraper: CategoryScraper, html: str) -> set[str]:
    """Identify archive products independently from SKU extraction.

    Category coverage must not depend on a product having a SKU. Product URLs are
    the primary identity; the legacy scraper keys are retained as a fallback.
    """
    if not html:
        return set()
    keys = set()
    for url in _PRODUCT_URL_PATTERN.findall(html):
        parts = urlsplit(url)
        path = parts.path.rstrip("/")
        keys.add(urlunsplit((parts.scheme, parts.netloc, path, "", "")))
    if keys:
        return keys
    try:
        return set(scraper._product_keys(html))
    except (AttributeError, TypeError, ValueError):
        return set()


def _facundo_jsf_pages(
    scraper: CategoryScraper,
    category_url: str,
    category_id: int,
    first_html: str,
    expected_count: int,
) -> list[str]:
    """Fetch every consecutive JSF page until the archive is actually exhausted.

    ``expected_count`` and published counts are validation targets, not limits.
    The site metadata can under-report pages, so a page is never skipped merely
    because a count-derived estimate says the category should have ended.
    """
    pages = [category_url]
    scraper._cache_category_html(category_url, first_html)
    seen_products = _product_keys(scraper, first_html)

    published_count = _published_product_count(first_html)
    target_count = max(int(expected_count or 0), published_count)

    try:
        found_posts, declared_pages, jsf_first_html = scraper._fetch_jsf_page(
            category_url, category_id, 1
        )
    except (KeyError, RuntimeError, TypeError, ValueError):
        found_posts, declared_pages, jsf_first_html = 0, 0, ""

    target_count = max(target_count, found_posts)
    if jsf_first_html:
        scraper._cache_category_html(category_url, jsf_first_html)
        seen_products.update(_product_keys(scraper, jsf_first_html))

    page = 2
    empty_or_repeat_pages = 0
    safety_limit = max(scraper.MAX_HIDDEN_PAGE_PROBES, declared_pages or 0, 2)
    while page <= safety_limit:
        page_url = scraper._jsf_page_url(category_url, page)
        try:
            found_posts, page_count, rendered_html = scraper._fetch_jsf_page(
                category_url, category_id, page
            )
        except (KeyError, RuntimeError, TypeError, ValueError):
            break

        target_count = max(target_count, found_posts)
        safety_limit = max(safety_limit, page_count)
        if not rendered_html:
            break

        page_keys = _product_keys(scraper, rendered_html)
        new_keys = page_keys.difference(seen_products)
        if not page_keys or not new_keys:
            # A repeated/empty JSF response marks the real end of consecutive pages.
            empty_or_repeat_pages += 1
            if empty_or_repeat_pages >= 1:
                break
        else:
            empty_or_repeat_pages = 0
            seen_products.update(new_keys)
            scraper._cache_category_html(page_url, rendered_html)
            pages.append(page_url)

        # If metadata says there are more pages, keep following it. If coverage is
        # still short, probing also continues; neither expected_count nor 25/page
        # arithmetic is allowed to truncate the archive.
        if page >= safety_limit and len(seen_products) < target_count:
            safety_limit = page + scraper.MAX_HIDDEN_PAGE_PROBES
        page += 1

    if target_count and len(seen_products) < target_count:
        raise RuntimeError(
            "Cobertura incompleta para "
            f"{category_url}: encontrados={len(seen_products)} esperados={target_count}."
        )
    return pages


def _generic_complete_pages(
    scraper: CategoryScraper,
    category_url: str,
    pages: list[str],
    expected_count: int,
) -> list[str]:
    """Continue consecutive public pages; expected_count is validation only."""
    if not pages:
        pages = [category_url]

    seen_products: set[str] = set()
    visited = set()
    first_html = ""
    for index, page_url in enumerate(pages):
        html = _safe_get_html(scraper, page_url)
        if index == 0:
            first_html = html
        seen_products.update(_product_keys(scraper, html))
        visited.add(page_url)

    target_count = max(int(expected_count or 0), _published_product_count(first_html))
    next_page = max((scraper._page_number(url) or 1 for url in pages), default=1) + 1
    for _ in range(scraper.MAX_HIDDEN_PAGE_PROBES):
        page_url = scraper._fallback_page_url(category_url, next_page)
        if page_url in visited:
            next_page += 1
            continue
        html = _safe_get_html(scraper, page_url)
        page_keys = _product_keys(scraper, html)
        new_keys = page_keys.difference(seen_products)
        if not page_keys or not new_keys:
            break
        scraper._cache_category_html(page_url, html)
        pages.append(page_url)
        visited.add(page_url)
        seen_products.update(new_keys)
        next_page += 1

    if target_count and len(seen_products) < target_count:
        raise RuntimeError(
            "Cobertura incompleta para "
            f"{category_url}: encontrados={len(seen_products)} esperados={target_count}."
        )
    return pages


def _get_category_pages(
    self: CategoryScraper, category_url: str, expected_count: int = 0
) -> list[str]:
    """Discover every archive page using page content as the source of truth."""
    first_html = _safe_get_html(self, category_url)
    if not first_html:
        return []
    category_id = self._category_id(first_html)
    if category_id is not None and self._is_facundo_url(category_url):
        return _facundo_jsf_pages(
            self, category_url, category_id, first_html, expected_count
        )

    self._cache_category_html(category_url, first_html)
    pages = _ORIGINAL_GET_CATEGORY_PAGES(self, category_url, expected_count=0)
    return _generic_complete_pages(self, category_url, pages, expected_count)


def activate() -> None:
    """Install the compatibility behavior once for the collectors package."""
    global _PATCHED
    if not _PATCHED:
        CategoryScraper.get_category_pages = _get_category_pages
        _PATCHED = True


activate()

__all__ = ["CategoryScraper", "activate", "pages_required"]
