"""Reliable pagination compatibility layer for Facundo category archives."""

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


def _get_category_pages(
    self: CategoryScraper,
    category_url: str,
    expected_count: int = 0,
) -> list[str]:
    """Delegate pagination to the scraper's authoritative pagination logic.

    ``expected_count`` is a coverage expectation, not a page-count ceiling.
    In particular, Facundo categories can publish more products than the
    category metadata supplied to the scraper.  The native JSF path already
    combines ``found_posts``, ``max_num_pages`` and declared pagination, so
    bypassing it here can incorrectly stop a category after page 1.
    """
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
