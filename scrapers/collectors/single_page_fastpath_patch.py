"""Safe fast path that reuses the fetched archive HTML as JSF page one."""

from __future__ import annotations

from . import category_pagination_patch as _pagination
from .category_scraper import CategoryScraper

_PATCHED = False
_ORIGINAL_JSF_CATEGORY_PAGES = _pagination._jsf_category_pages_with_probe


def _archive_first_page_is_complete(
    scraper: CategoryScraper,
    category_html: str,
    expected_count: int,
) -> tuple[bool, set[str]]:
    """Accept public page one only when its product count matches the target."""
    expected = max(int(expected_count or 0), 0)
    if expected <= 0:
        return False, set()

    product_keys = _pagination._page_product_keys(
        scraper,
        category_html,
        category_html,
    )
    expected_first_page = min(expected, scraper.PRODUCTS_PER_PAGE)
    if len(product_keys) != expected_first_page:
        return False, product_keys
    return True, product_keys


def _jsf_category_pages_archive_first_page_fastpath(
    self: CategoryScraper,
    category_url: str,
    category_id: int,
    expected_count: int,
    category_html: str = "",
) -> list[str]:
    """Skip redundant JSF page-one retrieval when the public page is complete."""
    usable, seen_product_keys = _archive_first_page_is_complete(
        self,
        category_html,
        expected_count,
    )
    if not usable:
        return _ORIGINAL_JSF_CATEGORY_PAGES(
            self,
            category_url,
            category_id,
            expected_count,
            category_html=category_html,
        )

    _pagination._remember_jsf_settings(category_id, category_html)
    pages = [category_url]
    self._cache_category_html(category_url, category_html)

    expected_pages = self._required_page_count(expected_count)
    declared_pages = max(
        self._declared_total_pages(category_html),
        self._pagination_max_page(category_html),
    )
    known_pages = max(declared_pages, expected_pages, 1)

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

    # Preserve the existing boundary probe so an underreported or hidden page
    # beyond the declared/expected range is still detected.
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
    """Install the archive-first-page fast path once."""
    global _PATCHED
    if _PATCHED:
        return
    _pagination._jsf_category_pages_with_probe = _jsf_category_pages_archive_first_page_fastpath
    _PATCHED = True


activate()

__all__ = ["activate"]
