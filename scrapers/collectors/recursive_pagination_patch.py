"""Recursive pagination recovery compatibility layer."""

from __future__ import annotations

from . import category_pagination_patch as _category_pagination_patch
from .category_scraper import CategoryScraper


def _candidate_page_urls(
    scraper: CategoryScraper,
    category_url: str,
    page_number: int,
    discovered_by_number: dict[int, str],
) -> list[str]:
    candidates: list[str] = []
    discovered_url = discovered_by_number.get(page_number)
    if discovered_url:
        candidates.append(discovered_url)
    for candidate in _category_pagination_patch._page_variants(category_url, page_number):
        if candidate not in candidates:
            candidates.append(candidate)
    return candidates


def _try_public_page(
    scraper: CategoryScraper,
    category_url: str,
    candidates: list[str],
    seen: set[str],
    discovered_by_number: dict[int, str],
) -> str | None:
    for page_url in candidates:
        html = _category_pagination_patch._safe_get_html(scraper, page_url)
        if not html:
            continue
        current = _category_pagination_patch._page_product_keys(scraper, html, page_url)
        new_keys = current - seen
        if not current or not new_keys:
            continue
        seen.update(current)
        scraper._cache_category_html(page_url, html)
        discovered = scraper._fallback_pagination_links(category_url, html)
        for url in discovered:
            number = scraper._page_number(url)
            if number is not None and number > 1:
                discovered_by_number.setdefault(number, url)
        return page_url
    return None


def _collect_direct_pages(
    scraper: CategoryScraper,
    category_url: str,
    first_html: str,
    expected_count: int,
) -> tuple[list[str], set[str]]:
    """Collect public pages and follow pagination discovered on intermediate pages."""
    expected_pages = _category_pagination_patch.pages_required(
        expected_count,
        scraper.PRODUCTS_PER_PAGE,
    )
    initial_keys = _category_pagination_patch._page_product_keys(
        scraper,
        first_html,
        category_url,
    )
    pages = [category_url]
    seen = set(initial_keys)

    discovered = scraper._fallback_pagination_links(category_url, first_html)
    discovered_by_number: dict[int, str] = {}
    for url in discovered:
        number = scraper._page_number(url)
        if number is not None and number > 1:
            discovered_by_number.setdefault(number, url)

    declared_pages = max(
        scraper._declared_total_pages(first_html),
        scraper._pagination_max_page(first_html),
        max(discovered_by_number, default=0),
        expected_pages,
    )

    for page_number in range(2, declared_pages + 1):
        candidates = _candidate_page_urls(
            scraper,
            category_url,
            page_number,
            discovered_by_number,
        )
        accepted_url = _try_public_page(
            scraper,
            category_url,
            candidates,
            seen,
            discovered_by_number,
        )
        if accepted_url is None:
            raise RuntimeError(
                f"No unique products found on public pagination page "
                f"{page_number} for {category_url}"
            )
        pages.append(accepted_url)
        declared_pages = max(
            declared_pages,
            max(discovered_by_number, default=0),
        )

    return pages, seen


def _get_category_pages(
    self: CategoryScraper,
    category_url: str,
    expected_count: int = 0,
) -> list[str]:
    """Preserve public fallback behavior while extending Facundo recovery."""
    first_html = _category_pagination_patch._safe_get_html(self, category_url)
    if not first_html:
        return []

    pages = [category_url]
    seen: set[str] = set()
    try:
        pages, seen = _collect_direct_pages(
            self,
            category_url,
            first_html,
            expected_count,
        )
    except RuntimeError:
        pages = [category_url]

    target = max(int(expected_count or 0), 0)
    has_product_data = bool(seen)

    if not self._is_facundo_url(category_url):
        if target <= 0:
            self._cache_category_html(category_url, first_html)
            return self._fallback_category_pages(
                category_url,
                first_html,
                expected_count,
            )
        if len(seen) >= target:
            return pages
        self._cache_category_html(category_url, first_html)
        return _category_pagination_patch._ORIGINAL_GET_CATEGORY_PAGES(
            self,
            category_url,
            expected_count=expected_count,
        )

    category_id = self._category_id(first_html)
    if category_id is None:
        return pages

    if target > 0 and len(seen) >= target:
        return pages
    if target <= 0 and has_product_data:
        self._cache_category_html(category_url, first_html)
    else:
        self._cache_category_html(category_url, first_html)
    return _category_pagination_patch._jsf_category_pages_with_probe(
        self,
        category_url,
        category_id,
        expected_count,
        category_html=first_html,
    )


_category_pagination_patch._collect_direct_pages = _collect_direct_pages
_category_pagination_patch.CategoryScraper.get_category_pages = _get_category_pages

__all__ = ["_collect_direct_pages"]
