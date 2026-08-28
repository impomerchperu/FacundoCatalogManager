"""Reliable pagination compatibility layer for Facundo category archives."""

import re

from .category_scraper import CategoryScraper

_PATCHED = False
_ORIGINAL_GET_CATEGORY_PAGES = CategoryScraper.get_category_pages
_PRODUCTS_IN_ARCHIVE_PATTERN = re.compile(
    r"Productos\s+en\s+Stock\s*(\d+)",
    re.IGNORECASE,
)


def pages_required(expected_count: int, products_per_page: int = 25) -> int:
    """Return the minimum number of pages required by a category count."""
    count = max(int(expected_count or 0), 0)
    per_page = max(int(products_per_page or 25), 1)
    if count == 0:
        return 0
    return (count + per_page - 1) // per_page


def _published_product_count(html: str) -> int:
    """Read the archive's own product total instead of trusting the menu count."""
    match = _PRODUCTS_IN_ARCHIVE_PATTERN.search(html or "")
    if not match:
        return 0
    try:
        return int(match.group(1))
    except (TypeError, ValueError):
        return 0


def _safe_get_html(scraper: CategoryScraper, url: str) -> str:
    try:
        return scraper.get_html(url)
    except Exception:
        return ""


def _page_product_count(scraper: CategoryScraper, html: str) -> int:
    if not html:
        return 0
    try:
        return len(scraper._product_keys(html))
    except (AttributeError, TypeError, ValueError):
        return 0


def _page_url_variants(scraper: CategoryScraper, category_url: str, page: int):
    variants = [scraper._fallback_page_url(category_url, page)]
    query_url = scraper._jsf_page_url(category_url, page)
    if query_url not in variants:
        variants.append(query_url)
    return variants


def _extend_public_archive_pages(
    scraper: CategoryScraper,
    category_url: str,
    pages: list[str],
    target_pages: int,
) -> list[str]:
    """Extend a partially discovered archive using real WooCommerce pages."""
    if target_pages <= len(pages):
        return pages

    known = set(pages)
    for page_number in range(2, target_pages + 1):
        if any(scraper._page_number(url) == page_number for url in known):
            continue

        selected_url = ""
        selected_html = ""
        for candidate in _page_url_variants(scraper, category_url, page_number):
            html = _safe_get_html(scraper, candidate)
            if not html:
                continue
            if _page_product_count(scraper, html) <= 0:
                continue
            selected_url = candidate
            selected_html = html
            break

        if not selected_url:
            raise RuntimeError(
                "Paginación incompleta para "
                f"{category_url}: no se pudo obtener la página {page_number}."
            )

        scraper._cache_category_html(selected_url, selected_html)
        pages.append(selected_url)
        known.add(selected_url)

    return pages


def _get_category_pages(
    self: CategoryScraper,
    category_url: str,
    expected_count: int = 0,
) -> list[str]:
    """Discover every published archive page before product consolidation.

    The count shown in the category menu is only a reference. Facundo's
    category archive exposes its actual total as ``Productos en Stock N``;
    that value is used to extend pagination when the public archive or native
    JSF path returned only the first page. Duplicates are consolidated later
    by product code, after all category occurrences have been collected.
    """
    pages = _ORIGINAL_GET_CATEGORY_PAGES(
        self,
        category_url,
        expected_count=expected_count,
    )
    if not self._is_facundo_url(category_url):
        return pages

    first_html = _safe_get_html(self, category_url)
    published_count = _published_product_count(first_html)
    target_pages = pages_required(
        max(published_count, int(expected_count or 0)),
        self.PRODUCTS_PER_PAGE,
    )
    return _extend_public_archive_pages(
        self,
        category_url,
        pages,
        max(target_pages, len(pages)),
    )


def activate() -> None:
    """Install the compatibility behavior once for the collectors package."""
    global _PATCHED
    if _PATCHED:
        return
    CategoryScraper.get_category_pages = _get_category_pages
    _PATCHED = True


activate()

__all__ = ["CategoryScraper", "activate", "pages_required"]
