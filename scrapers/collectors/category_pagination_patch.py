"""Reliable pagination compatibility layer for Facundo category archives.

The category index publishes an expected product count.  Facundo's archive
uses JetSmartFilters/Bricks, but the public WooCommerce ``/page/N/`` archive
is also available and is materially more reliable than the AJAX endpoint.

Pagination therefore follows this order for every page after page 1:
1. public WooCommerce ``/page/N/``;
2. WooCommerce ``?product-page=N``;
3. JetSmartFilters AJAX.

Every accepted page must contain products not already seen.  This prevents
an AJAX response that silently repeats page 1 from being counted as coverage.
"""

from __future__ import annotations

import requests

from .category_scraper import CategoryScraper


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
    """Return stable identities for products present in one archive page."""
    if not html:
        return set()

    soup = self._parse(html)
    keys: set[str] = set()

    # Prefer the project's product-block extractor when available because it
    # knows the exact archive markup.  Keep a direct-link fallback because
    # pagination validation must not depend on an extractor being able to
    # parse every variation returned by JetSmartFilters.
    extractor = getattr(self, "product_block_extractor", None)
    if extractor is not None:
        try:
            cards = (
                extractor(soup)
                if callable(extractor)
                else extractor.extract(soup)
            )
        except (AttributeError, TypeError, ValueError):
            cards = []

        for card in cards or []:
            sku = card.select_one(".sku") if hasattr(card, "select_one") else None
            code = sku.get_text(" ", strip=True) if sku is not None else ""
            if code:
                keys.add(f"code:{code.casefold()}")
                continue
            link = (
                card.select_one('a[href*="/producto/"]')
                if hasattr(card, "select_one")
                else None
            )
            href = link.get("href", "") if link is not None else ""
            if href:
                keys.add(f"url:{href.casefold()}")

    for link in soup.select('a[href*="/producto/"]'):
        href = link.get("href", "").strip()
        if href:
            keys.add(f"url:{href.casefold().rstrip('/')}")

    return keys


def _get_direct_page_html(self: CategoryScraper, page_url: str) -> str:
    """Fetch a public archive page and accept it only when it has products."""
    try:
        html = self.get_html(page_url)
    except requests.RequestException:
        return ""
    return html if _archive_product_keys(self, html) else ""


def _candidate_page_urls(category_url: str, page_number: int) -> tuple[str, ...]:
    """Return public archive URL variants supported by WooCommerce."""
    base = category_url.rstrip("/")
    return (
        f"{base}/page/{page_number}/",
        f"{base}?product-page={page_number}",
        f"{base}?paged={page_number}",
    )


def _fetch_non_duplicate_page(
    self: CategoryScraper,
    category_url: str,
    category_id: int,
    page_number: int,
    seen_keys: set[str],
) -> tuple[str, str, set[str]]:
    """Return the first page representation containing new products."""
    for page_url in _candidate_page_urls(category_url, page_number):
        html = _get_direct_page_html(self, page_url)
        page_keys = _archive_product_keys(self, html)
        if page_keys and not page_keys.issubset(seen_keys):
            return page_url, html, page_keys

    try:
        _, _, rendered_html = self._fetch_jsf_page(
            category_url,
            category_id,
            page_number,
        )
    except requests.RequestException:
        rendered_html = ""

    page_keys = _archive_product_keys(self, rendered_html)
    if page_keys and not page_keys.issubset(seen_keys):
        page_url = self._jsf_page_url(category_url, page_number)
        return page_url, rendered_html, page_keys

    return "", "", set()


def _get_category_pages(
    self: CategoryScraper,
    category_url: str,
    expected_count: int = 0,
) -> list[str]:
    """Traverse all required category pages without accepting duplicates."""
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

    first_keys = _archive_product_keys(self, category_html)
    required_pages = pages_required(
        expected,
        getattr(self, "PRODUCTS_PER_PAGE", 25),
    )
    if required_pages <= 1:
        return [category_url]

    category_id = self._category_id(category_html) or 0
    pages = [category_url]
    seen_keys = set(first_keys)

    for page_number in range(2, required_pages + 1):
        page_url, rendered_html, page_keys = _fetch_non_duplicate_page(
            self,
            category_url,
            category_id,
            page_number,
            seen_keys,
        )
        if not page_url or not rendered_html or not page_keys:
            raise RuntimeError(
                "No se pudo obtener una página nueva de productos: "
                f"{category_url} página {page_number}/{required_pages}."
            )

        self._cache_category_html(page_url, rendered_html)
        seen_keys.update(page_keys)
        pages.append(page_url)

    if len(pages) != required_pages:
        raise RuntimeError(
            f"Paginación incompleta para {category_url}: "
            f"{len(pages)}/{required_pages} páginas."
        )

    if len(seen_keys) < expected:
        raise RuntimeError(
            f"Cobertura incompleta para {category_url}: "
            f"{len(seen_keys)}/{expected} productos detectados."
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
