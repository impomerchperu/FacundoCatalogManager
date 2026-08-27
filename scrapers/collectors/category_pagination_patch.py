"""Category pagination compatibility layer.

The category index publishes the authoritative product count for each
category. For categories larger than one page, traverse exactly the pages
required by that category's own published count. JetSmartFilters is used for
those additional pages so page 2+ cannot silently repeat the first archive.
"""

import requests

from .category_scraper import CategoryScraper


_PATCHED = False
_ORIGINAL_GET_CATEGORY_PAGES = CategoryScraper.get_category_pages


def pages_required(expected_count: int, products_per_page: int = 25) -> int:
    """Return the number of pages required by one category's own count."""
    count = max(int(expected_count or 0), 0)
    if count == 0:
        return 0
    return (count + products_per_page - 1) // products_per_page


def _archive_product_keys(self: CategoryScraper, html: str) -> set[str]:
    """Return stable identities for real product cards in one archive page."""
    extractor = getattr(self, "product_block_extractor", None)
    if extractor is None:
        return set()
    try:
        soup = self._parse(html)
        cards = extractor(soup) if callable(extractor) else extractor.extract(soup)
    except (AttributeError, TypeError, ValueError):
        return set()

    keys: set[str] = set()
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
            continue
        try:
            text = " ".join(card.stripped_strings).strip().casefold()
        except AttributeError:
            text = ""
        if text:
            keys.add(f"text:{text}")
    return keys


def _get_direct_page_html(self: CategoryScraper, page_url: str) -> str:
    """Try the public category URL when a JSF page is empty or duplicated."""
    try:
        html = self.get_html(page_url)
    except requests.RequestException:
        return ""
    return html if html and _archive_product_keys(self, html) else ""


def _get_category_pages(
    self: CategoryScraper,
    category_url: str,
    expected_count: int = 0,
) -> list[str]:
    """Traverse the pages required by this category's published count."""
    expected = max(int(expected_count or 0), 0)
    if expected == 0:
        return _ORIGINAL_GET_CATEGORY_PAGES(self, category_url, expected_count=0)

    category_html = self.get_html(category_url)
    if not category_html:
        return []
    self._cache_category_html(category_url, category_html)

    first_keys = _archive_product_keys(self, category_html)
    if len(first_keys) >= expected:
        return [category_url]

    required_pages = pages_required(
        expected,
        getattr(self, "PRODUCTS_PER_PAGE", 25),
    )
    if required_pages <= 1:
        return [category_url]

    category_id = self._category_id(category_html)
    if category_id is None:
        category_id = 0

    pages = [category_url]
    seen_keys = set(first_keys)
    for page_number in range(2, required_pages + 1):
        page_url = self._jsf_page_url(category_url, page_number)
        _, _, rendered_html = self._fetch_jsf_page(
            category_url,
            category_id,
            page_number,
        )
        page_keys = _archive_product_keys(self, rendered_html)
        if not page_keys or page_keys.issubset(seen_keys):
            direct_html = _get_direct_page_html(self, page_url)
            direct_keys = _archive_product_keys(self, direct_html)
            if direct_keys and not direct_keys.issubset(seen_keys):
                rendered_html = direct_html
                page_keys = direct_keys

        if not rendered_html or not page_keys:
            raise RuntimeError(
                "No se pudo obtener productos de la página "
                f"{page_number}/{required_pages} de {category_url}."
            )
        if page_keys.issubset(seen_keys):
            raise RuntimeError(
                "La página "
                f"{page_number}/{required_pages} de {category_url} "
                "repitió los productos de una página anterior."
            )

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
