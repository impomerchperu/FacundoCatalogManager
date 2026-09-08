"""Recursive public pagination recovery compatibility layer."""

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
    page_number: int,
    candidates: list[str],
    seen: set[str],
    discovered_by_number: dict[int, str],
) -> bool:
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
        return True
    return False


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

    page_number = 2
    while page_number <= declared_pages:
        candidates = _candidate_page_urls(
            scraper,
            category_url,
            page_number,
            discovered_by_number,
        )
        if _try_public_page(
            scraper,
            category_url,
            page_number,
            candidates,
            seen,
            discovered_by_number,
        ):
            pages.append(
                discovered_by_number.get(
                    page_number,
                    _category_pagination_patch._page_variants(
                        category_url,
                        page_number,
                    )[0],
                )
            )
            declared_pages = max(
                declared_pages,
                max(discovered_by_number, default=0),
            )
        else:
            raise RuntimeError(
                f"No unique products found on public pagination page "
                f"{page_number} for {category_url}"
            )
        page_number += 1

    return pages, seen


_category_pagination_patch._collect_direct_pages = _collect_direct_pages

__all__ = ["_collect_direct_pages"]
