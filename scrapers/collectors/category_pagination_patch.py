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


def _page_product_count(scraper: CategoryScraper, html: str) -> int:
    return len(_page_product_keys(scraper, html))


def _page_url_variants(scraper: CategoryScraper, category_url: str, page: int):
    variants = [scraper._fallback_page_url(category_url, page)]
    query_url = scraper._jsf_page_url(category_url, page)
    if query_url not in variants:
        variants.append(query_url)
    return variants


def _facundo_jsf_pages(
    scraper: CategoryScraper,
    category_url: str,
    category_id: int,
    first_html: str,
    expected_count: int,
) -> list[str]:
    """Use the already fetched archive page, then continue with native JSF."""
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

    # Page 1 is already available from the public archive. JSF is only used
    # for the remaining pages, avoiding a redundant page-1 AJAX request.
    next_page = 2
    declared_pages = required_pages
    while next_page <= declared_pages:
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
    seen_products: set[str] = set()
    for page_url in pages:
        seen_products.update(
            _page_product_keys(scraper, _safe_get_html(scraper, page_url))
        )

    for page_number in range(2, target_pages + 1):
        if any(scraper._page_number(url) == page_number for url in known):
            continue

        selected_url = ""
        selected_html = ""
        for candidate in _page_url_variants(scraper, category_url, page_number):
            html = _safe_get_html(scraper, candidate)
            page_keys = _page_product_keys(scraper, html)
            if not page_keys or not page_keys.difference(seen_products):
                continue
            selected_url = candidate
            selected_html = html
            seen_products.update(page_keys)
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


def _probe_one_more_public_page(
    scraper: CategoryScraper,
    category_url: str,
    pages: list[str],
) -> list[str]:
    """Probe one consecutive page when the archive gave no explicit total."""
    page_numbers = [
        number
        for number in (scraper._page_number(url) for url in pages)
        if number is not None
    ]
    next_page = max(page_numbers, default=1) + 1
    for candidate in _page_url_variants(scraper, category_url, next_page):
        html = _safe_get_html(scraper, candidate)
        if not html or _page_product_count(scraper, html) <= 0:
            continue
        scraper._cache_category_html(candidate, html)
        pages.append(candidate)
        return pages
    return pages


def _get_category_pages(
    self: CategoryScraper,
    category_url: str,
    expected_count: int = 0,
) -> list[str]:
    """Discover all published archive pages before product consolidation."""
    if self._is_facundo_url(category_url):
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

    pages = _ORIGINAL_GET_CATEGORY_PAGES(
        self,
        category_url,
        expected_count=expected_count,
    )

    # Keep the generic fallback resilient to archives that omit pagination
    # controls and expose a partial final page. This is intentionally a single
    # probe so ordinary scrapes do not turn into an open-ended crawl.
    if expected_count > 0 and len(pages) == pages_required(
        expected_count, self.PRODUCTS_PER_PAGE
    ):
        return _probe_one_more_public_page(self, category_url, pages)
    return pages


def activate() -> None:
    """Install the compatibility behavior once for the collectors package."""
    global _PATCHED
    if _PATCHED:
        return
    CategoryScraper.get_category_pages = _get_category_pages
    _PATCHED = True


activate()

__all__ = ["CategoryScraper", "activate", "pages_required"]
