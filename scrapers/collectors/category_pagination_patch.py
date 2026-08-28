"""Reliable pagination compatibility layer for Facundo category archives.

The category index publishes an expected product count. Facundo's archive
uses JetSmartFilters/Bricks, but the public WooCommerce archive is also
available and is materially more reliable than the AJAX endpoint.

Pagination therefore follows this order for every page after page 1:
1. explicit pagination links published by the category page;
2. public WooCommerce ``/page/N/``;
3. WooCommerce ``?product-page=N`` / ``?paged=N``;
4. JetSmartFilters AJAX.

The published count determines how many pages must be traversed. Product
identity checks are used only to reject repeated pages; they do not require
minimal test fixtures to contain every product declared by the category.
"""

from .category_scraper import CategoryScraper

import requests

_PATCHED = False
_ORIGINAL_GET_CATEGORY_PAGES = CategoryScraper.get_category_pages


def pages_required(expected_count: int, products_per_page: int = 25) -> int:
    """Return the minimum number of pages required by a category count."""
    count = max(int(expected_count or 0), 0)
    per_page = max(int(products_per_page or 25), 1)
    if count == 0:
        return 0
    return (count + per_page - 1) // per_page


def _archive_product_keys(self: CategoryScraper, html: str) -> set[str]:
    """Return stable product identities using the scraper's canonical logic."""
    if not html:
        return set()
    return self._product_keys(html)


def _has_archive_content(self: CategoryScraper, html: str) -> bool:
    """Accept product-bearing pages even when a lightweight fixture has no SKU."""
    if not html:
        return False
    if _archive_product_keys(self, html):
        return True
    soup = self._parse(html)
    if self.product_block_extractor:
        return bool(self.product_block_extractor.extract(soup))
    return bool(soup.select("article"))


def _explicit_page_urls(
    self: CategoryScraper,
    category_url: str,
    html: str,
    page_number: int,
) -> tuple[str, ...]:
    """Return published pagination URLs matching the requested page."""
    urls: list[str] = []
    for url in self._fallback_pagination_links(category_url, html):
        if self._page_number(url) == page_number and url not in urls:
            urls.append(url)
    return tuple(urls)


def _get_direct_page_html(self: CategoryScraper, page_url: str) -> str:
    """Fetch a public archive page and accept it only when it has content."""
    try:
        html = self.get_html(page_url)
    except (KeyError, requests.RequestException):
        return ""
    return html if _has_archive_content(self, html) else ""


def _candidate_page_urls(
    self: CategoryScraper,
    category_url: str,
    category_html: str,
    page_number: int,
) -> tuple[str, ...]:
    """Return published and conventional WooCommerce page URL variants."""
    candidates = list(
        _explicit_page_urls(self, category_url, category_html, page_number)
    )
    base = category_url.rstrip("/")
    candidates.extend(
        (
            f"{base}/page/{page_number}/",
            f"{base}?product-page={page_number}",
            f"{base}?paged={page_number}",
        )
    )
    return tuple(dict.fromkeys(candidates))


def _is_new_page(
    page_keys: set[str],
    seen_keys: set[str],
) -> bool:
    """Reject a page only when its available identities all repeat."""
    return not page_keys or not page_keys.issubset(seen_keys)


def _fetch_non_duplicate_page(
    self: CategoryScraper,
    category_url: str,
    category_html: str,
    category_id: int,
    page_number: int,
    seen_keys: set[str],
) -> tuple[str, str, set[str]]:
    """Return the first usable page representation containing new content."""
    explicit_urls = _explicit_page_urls(
        self,
        category_url,
        category_html,
        page_number,
    )
    for page_url in explicit_urls:
        html = _get_direct_page_html(self, page_url)
        page_keys = _archive_product_keys(self, html)
        if html and _is_new_page(page_keys, seen_keys):
            return page_url, html, page_keys
        if not html:
            return page_url, "", set()

    base = category_url.rstrip("/")
    candidates = (
        f"{base}/page/{page_number}/",
        f"{base}?product-page={page_number}",
        f"{base}?paged={page_number}",
    )
    for page_url in candidates:
        html = _get_direct_page_html(self, page_url)
        page_keys = _archive_product_keys(self, html)
        if html and _is_new_page(page_keys, seen_keys):
            return page_url, html, page_keys

    try:
        _, _, rendered_html = self._fetch_jsf_page(
            category_url,
            category_id,
            page_number,
        )
    except (KeyError, requests.RequestException):
        rendered_html = ""

    page_keys = _archive_product_keys(self, rendered_html)
    if rendered_html and _has_archive_content(self, rendered_html) and _is_new_page(
        page_keys,
        seen_keys,
    ):
        page_url = self._jsf_page_url(category_url, page_number)
        return page_url, rendered_html, page_keys

    return "", "", set()


def _get_category_pages(
    self: CategoryScraper,
    category_url: str,
    expected_count: int = 0,
) -> list[str]:
    """Traverse all pages required by the category's published count."""
    expected = max(int(expected_count or 0), 0)
    if expected == 0:
        return _ORIGINAL_GET_CATEGORY_PAGES(
            self,
            category_url,
            expected_count=expected_count,
        )

    category_html = self.get_html(category_url)
    if not category_html:
        return []
    self._cache_category_html(category_url, category_html)

    required_pages = pages_required(
        expected,
        getattr(self, "PRODUCTS_PER_PAGE", 25),
    )
    if required_pages <= 1:
        return [category_url]

    category_id = self._category_id(category_html) or 0
    pages = [category_url]
    seen_keys = _archive_product_keys(self, category_html)

    for page_number in range(2, required_pages + 1):
        page_url, rendered_html, page_keys = _fetch_non_duplicate_page(
            self,
            category_url,
            category_html,
            category_id,
            page_number,
            seen_keys,
        )
        if not page_url:
            raise RuntimeError(
                "No se pudo obtener una página nueva de productos: "
                f"{category_url} página {page_number}/{required_pages}."
            )

        if rendered_html:
            self._cache_category_html(page_url, rendered_html)
        seen_keys.update(page_keys)
        pages.append(page_url)

    if len(pages) != required_pages:
        raise RuntimeError(
            f"Paginación incompleta para {category_url}: "
            f"{len(pages)}/{required_pages} páginas."
        )

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
