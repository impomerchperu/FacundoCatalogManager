"""Category pagination compatibility layer.

Facundo's category archive already renders the complete category product
collection in the initial HTML. The JSF endpoint is only needed when the
archive HTML does not contain the category's published product count.
"""

from typing import Any

from .category_scraper import CategoryScraper


_ORIGINAL_GET_CATEGORY_PAGES = CategoryScraper.get_category_pages
_PATCHED = False


def pages_required(expected_count: int, products_per_page: int = 25) -> int:
    """Return pages required by one category's own product count."""
    count = max(int(expected_count or 0), 0)
    if count == 0:
        return 0
    return (count + products_per_page - 1) // products_per_page


def _get_category_pages(
    self: CategoryScraper,
    category_url: str,
    expected_count: int = 0,
) -> list[str]:
    """Prefer the complete category archive before falling back to JSF."""
    category_html = self.get_html(category_url)
    if not category_html:
        return []

    expected = max(int(expected_count or 0), 0)
    product_count = len(self._product_keys(category_html))

    if expected > 0 and product_count >= expected:
        self._cache_category_html(category_url, category_html)
        return [category_url]

    self._cache_category_html(category_url, category_html)
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
