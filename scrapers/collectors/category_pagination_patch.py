"""Reliable pagination compatibility layer for category archives."""

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
    """Read the archive's own product total instead of the menu count."""
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
    except (AttributeError, RuntimeError, TypeError, ValueError):
        return ""


def _page_product_keys(scraper: CategoryScraper, html: str) -> set[str]:
    if not html:
        return set()
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
    """Use the public first page, then native JSF for every required page."""
    pages = [category_url]
    scraper._cache_category_html(category_url, first_html)
    seen_products = _page_product_keys(scraper, first_html)
    first_count = len(seen_products)

    if first_count == 0:
        raise RuntimeError(
            "JetSmartFilters no encontró productos en la primera página de "
            f"{category_url}."
        )

    required_pages = pages_required(
        max(int(expected_count or 0), first_count),
        scraper.PRODUCTS_PER_PAGE,
    )
    published_count = _published_product_count(first_html)
    if published_count > 0:
        required_pages = max(
            required_pages,
            pages_required(published_count, scraper.PRODUCTS_PER_PAGE),
        )

    try:
        _, jsf_max_pages, jsf_first_html = scraper._fetch_jsf_page(
            category_url, category_id, 1
        )
        jsf_first_available = bool(jsf_first_html)
    except (KeyError, RuntimeError, TypeError, ValueError):
        jsf_first_html = ""
        jsf_max_pages = 0
        jsf_first_available = False

    if jsf_first_html:
        jsf_first_keys = _page_product_keys(scraper, jsf_first_html)
        if jsf_first_keys:
            seen_products.update(jsf_first_keys)

    declared_pages = max(required_pages, jsf_max_pages)
    if not jsf_first_available and declared_pages < 2:
        declared_pages = 2

    next_page = 2
    target_count = max(int(expected_count or 0), 0)
    while next_page <= declared_pages or (
        target_count > 0 and len(seen_products) < target_count
    ):
        page_url = scraper._jsf_page_url(category_url, next_page)
        _, jsf_max_pages, rendered_html = scraper._fetch_jsf_page(
            category_url, category_id, next_page
        )
        if not rendered_html:
            raise RuntimeError(
                "JetSmartFilters no devolvió contenido para "
                f"{category_url} en la página {next_page}."
            )

        page_keys = _page_product_keys(scraper, rendered_html)
        if not page_keys or not page_keys.difference(seen_products):
            raise RuntimeError(
                "Paginación repetida para "
                f"{category_url}: la página {next_page} "
                "no contiene productos nuevos."
            )

        seen_products.update(page_keys)
        scraper._cache_category_html(page_url, rendered_html)
        pages.append(page_url)
        declared_pages = max(declared_pages, jsf_max_pages)
        next_page += 1

    return pages


def _get_category_pages(
    self: CategoryScraper,
    category_url: str,
    expected_count: int = 0,
) -> list[str]:
    """Discover all published archive pages before product consolidation."""
    if self._is_facundo_url(category_url):
        if not expected_count:
            return _ORIGINAL_GET_CATEGORY_PAGES(
                self,
                category_url,
                expected_count=expected_count,
            )

        first_html = _safe_get_html(self, category_url)
        if not first_html:
            return []
        category_id = self._category_id(first_html)
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
            first_html,
            expected_count,
        )

    return _ORIGINAL_GET_CATEGORY_PAGES(
        self,
        category_url,
        expected_count=expected_count,
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
