"""Category pagination compatibility layer.

The category index publishes the authoritative product count for each
category. For categories larger than one page, traverse exactly the pages
required by that category's own published count. JetSmartFilters is used for
those additional pages so page 2+ cannot silently repeat the first archive.
"""

from .category_scraper import CategoryScraper


_PATCHED = False
_ORIGINAL_GET_CATEGORY_PAGES = CategoryScraper.get_category_pages


def pages_required(expected_count: int, products_per_page: int = 25) -> int:
    """Return the number of pages required by one category's own count."""
    count = max(int(expected_count or 0), 0)
    if count == 0:
        return 0
    return (count + products_per_page - 1) // products_per_page


def _archive_product_count(self: CategoryScraper, html: str) -> int:
    """Count real product blocks instead of SKU-like text in the whole HTML."""
    extractor = getattr(self, "product_block_extractor", None)
    if extractor is None:
        return 0
    try:
        soup = self._parse(html)
        cards = (
            extractor(soup) if callable(extractor) else extractor.extract(soup)
        )
        return len(cards or [])
    except (AttributeError, TypeError, ValueError):
        return 0


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

    archive_count = _archive_product_count(self, category_html)
    if archive_count >= expected:
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
    for page_number in range(2, required_pages + 1):
        page_url = self._jsf_page_url(category_url, page_number)
        _, _, rendered_html = self._fetch_jsf_page(
            category_url,
            category_id,
            page_number,
        )
        if not rendered_html:
            raise RuntimeError(
                "No se pudo obtener la página "
                f"{page_number}/{required_pages} de {category_url}."
            )
        self._cache_category_html(page_url, rendered_html)
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
