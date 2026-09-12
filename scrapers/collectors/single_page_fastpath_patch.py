"""Safe fast path for categories whose first HTML is a complete single page."""

from __future__ import annotations

from . import category_pagination_patch as _pagination
from .category_scraper import CategoryScraper

_PATCHED = False
_ORIGINAL_JSF_CATEGORY_PAGES = _pagination._jsf_category_pages_with_probe


def _single_page_html_is_complete(
    scraper: CategoryScraper,
    category_html: str,
    expected_count: int,
) -> bool:
    """Use the archive HTML only when it exactly matches a single-page target."""
    expected = max(int(expected_count or 0), 0)
    if expected <= 0 or expected > scraper.PRODUCTS_PER_PAGE:
        return False

    declared_pages = max(
        scraper._declared_total_pages(category_html),
        scraper._pagination_max_page(category_html),
    )
    if declared_pages > 1:
        return False

    product_keys = _pagination._page_product_keys(
        scraper,
        category_html,
        category_html,
    )
    return len(product_keys) == expected


def _jsf_category_pages_single_page_fastpath(
    self: CategoryScraper,
    category_url: str,
    category_id: int,
    expected_count: int,
    category_html: str = "",
) -> list[str]:
    """Skip redundant JSF page-one retrieval only for an exact single-page match."""
    if not _single_page_html_is_complete(self, category_html, expected_count):
        return _ORIGINAL_JSF_CATEGORY_PAGES(
            self,
            category_url,
            category_id,
            expected_count,
            category_html=category_html,
        )

    _pagination._remember_jsf_settings(category_id, category_html)
    pages = [category_url]
    seen_product_keys = _pagination._page_product_keys(
        self,
        category_html,
        category_url,
    )
    self._cache_category_html(category_url, category_html)

    # Preserve the existing boundary probe: a hidden second page must still
    # be detected before this category is considered complete.
    boundary_page = 2
    has_new_products, new_product_keys = _pagination._probe_boundary_page(
        self,
        category_url,
        category_id,
        boundary_page,
        seen_product_keys,
    )
    if has_new_products:
        seen_product_keys.update(new_product_keys)
        pages.append(self._jsf_page_url(category_url, boundary_page))
    return pages


def activate() -> None:
    """Install the single-page fast path once."""
    global _PATCHED
    if _PATCHED:
        return
    _pagination._jsf_category_pages_with_probe = _jsf_category_pages_single_page_fastpath
    _PATCHED = True


activate()

__all__ = ["activate"]
