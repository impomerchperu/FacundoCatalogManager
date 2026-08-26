"""Category pagination compatibility layer.

Facundo's category archive can contain the complete product table in its
initial HTML. Use that archive only when the real product-card extractor
confirms that it contains the category's published product count. Otherwise
fall back to the JSF pagination path.
"""

from .category_scraper import CategoryScraper


_ORIGINAL_GET_CATEGORY_PAGES = CategoryScraper.get_category_pages
_PATCHED = False


def pages_required(expected_count: int, products_per_page: int = 25) -> int:
    """Return pages required by one category's own product count."""
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
        if callable(extractor):
            cards = extractor(soup)
        else:
            cards = extractor.extract(soup)
        return len(cards or [])
    except (AttributeError, TypeError, ValueError):
        return 0


def _get_category_pages(
    self: CategoryScraper,
    category_url: str,
    expected_count: int = 0,
) -> list[str]:
    """Prefer a complete archive only after validating actual product blocks."""
    category_html = self.get_html(category_url)
    if not category_html:
        return []

    expected = max(int(expected_count or 0), 0)
    archive_count = _archive_product_count(self, category_html)
    self._cache_category_html(category_url, category_html)

    if expected > 0 and archive_count >= expected:
        return [category_url]

    return _ORIGINAL_GET_CATEGORY_PAGES(
        self,
        category_url,
        expected_count=expected,
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
