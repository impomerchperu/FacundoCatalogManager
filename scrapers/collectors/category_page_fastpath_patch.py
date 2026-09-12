"""Safe category-page fast path that avoids redundant JSF page-one requests."""

from __future__ import annotations

from . import category_pagination_patch as _pagination
from .category_scraper import CategoryScraper

_PATCHED = False
_ORIGINAL_JSF_CATEGORY_PAGES = _pagination._jsf_category_pages_with_probe


def _known_page_count(
    scraper: CategoryScraper,
    category_html: str,
    expected_count: int,
) -> int:
    """Keep the same page-count floor used by the existing pagination logic."""
    return max(
        scraper._required_page_count(expected_count),
        scraper._declared_total_pages(category_html),
        scraper._pagination_max_page(category_html),
        1,
    )


def _fast_jsf_category_pages(
    self: CategoryScraper,
    category_url: str,
    category_id: int,
    expected_count: int,
    category_html: str = "",
) -> list[str]:
    """Reuse a valid page-one archive response before falling back to JSF page one."""
    if expected_count <= 0 or not category_html:
        return _ORIGINAL_JSF_CATEGORY_PAGES(
            self,
            category_url,
            category_id,
            expected_count,
            category_html=category_html,
        )

    _pagination._remember_jsf_settings(category_id, category_html)
    first_product_keys = _pagination._page_product_keys(
        self,
        category_html,
        category_url,
    )
    if not first_product_keys:
        return _ORIGINAL_JSF_CATEGORY_PAGES(
            self,
            category_url,
            category_id,
            expected_count,
            category_html=category_html,
        )

    known_pages = _known_page_count(self, category_html, expected_count)
    pages = [category_url]
    seen_product_keys = set(first_product_keys)
    self._cache_category_html(category_url, category_html)

    for page_number in range(2, known_pages + 1):
        page_url = self._jsf_page_url(category_url, page_number)
        _, _, rendered_html = _pagination._walk_jsf_page(
            self,
            category_url,
            category_id,
            page_number,
        )
        if not rendered_html:
            raise RuntimeError(
                f"Empty JSF pagination page {page_number} for {category_url}"
            )
        current_product_keys = _pagination._page_product_keys(
            self,
            rendered_html,
            page_url,
        )
        if not current_product_keys:
            raise RuntimeError(
                f"No products found on JSF pagination page {page_number} for {category_url}"
            )
        new_product_keys = current_product_keys - seen_product_keys
        if not new_product_keys:
            raise RuntimeError(
                f"Repeated JSF pagination page {page_number} for {category_url}"
            )
        seen_product_keys.update(current_product_keys)
        self._cache_category_html(page_url, rendered_html)
        pages.append(page_url)

    boundary_page = known_pages + 1
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
    """Install the category page-one fast path once."""
    global _PATCHED
    if _PATCHED:
        return
    _pagination._jsf_category_pages_with_probe = _fast_jsf_category_pages
    _PATCHED = True


activate()

__all__ = ["activate"]
