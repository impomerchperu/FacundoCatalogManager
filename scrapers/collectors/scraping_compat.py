"""Runtime compatibility fixes for the Facundo catalog scraper."""

import re

from scrapers.extractors.product_extractor import ProductExtractor

from .category_pagination_patch import _facundo_direct_pages
from .category_scraper import CategoryScraper

_PRODUCT_URL_PATTERN = re.compile(
    r'href=["\']([^"\']*/producto/[^"\'#?]+/?)[^"\']*["\']',
    re.IGNORECASE,
)


def _normalize_code_candidate(cls, text: str) -> str:
    """Accept SKU codes made of letters/digits separated by hyphens."""
    candidate = str(text).strip().strip(".,:;()[]{}")
    if not cls._CODE_PATTERN.fullmatch(candidate):
        return ""
    if not any(char.isalpha() for char in candidate):
        return ""
    return candidate.upper()


def _product_keys(html: str) -> set[str]:
    return {
        match.group(1).rstrip("/").casefold()
        for match in _PRODUCT_URL_PATTERN.finditer(html or "")
    }


def _required_pages(count: int, per_page: int = 25) -> int:
    count = max(int(count or 0), 0)
    return max((count + per_page - 1) // per_page, 1)


def _facundo_category_pages(
    scraper: CategoryScraper,
    category_url: str,
    category_id: int,
    first_html: str,
    expected_count: int,
) -> list[str]:
    """Fetch declared JSF pages and probe one sentinel for underreported totals."""
    pages = [category_url]
    scraper._cache_category_html(category_url, first_html)

    found_posts, declared_pages, rendered_html = scraper._fetch_jsf_page(
        category_url, category_id, 1
    )
    if rendered_html:
        scraper._cache_category_html(category_url, rendered_html)

    seen = _product_keys(rendered_html)
    required = max(
        _required_pages(expected_count),
        _required_pages(found_posts),
        int(declared_pages or 1),
    )
    declared_pages = max(int(declared_pages or 0), 1)
    published_pages = _required_pages(found_posts)

    for page in range(2, required + 1):
        page_url = scraper._jsf_page_url(category_url, page)
        try:
            _, page_count, page_html = scraper._fetch_jsf_page(
                category_url, category_id, page
            )
        except (KeyError, RuntimeError, TypeError, ValueError):
            break
        required = max(required, int(page_count or 0))
        if not page_html:
            break
        current = _product_keys(page_html)
        if current and not current - seen:
            raise RuntimeError(
                f"Repeated JSF pagination page {page} for {category_url}"
            )
        scraper._cache_category_html(page_url, page_html)
        pages.append(page_url)
        seen.update(current)

    if published_pages > declared_pages:
        sentinel_page = required + 1
        sentinel_url = scraper._jsf_page_url(category_url, sentinel_page)
        try:
            _, _, sentinel_html = scraper._fetch_jsf_page(
                category_url, category_id, sentinel_page
            )
        except (KeyError, RuntimeError, TypeError, ValueError):
            sentinel_html = ""
        if sentinel_html:
            sentinel_keys = _product_keys(sentinel_html)
            if sentinel_keys and not sentinel_keys - seen:
                scraper._cache_category_html(sentinel_url, sentinel_html)
                pages.append(sentinel_url)

    return pages


def _get_category_pages(self, category_url: str, expected_count: int = 0) -> list[str]:
    first_html = self.get_html(category_url)
    if not first_html:
        return []

    if self._is_facundo_url(category_url):
        direct_pages, direct_count = _facundo_direct_pages(
            self,
            category_url,
            first_html,
            expected_count,
        )
        expected = max(int(expected_count or 0), 0)
        if len(direct_pages) > 1 or expected == 0 or direct_count >= expected:
            return direct_pages

    category_id = self._category_id(first_html)
    if category_id is None or not self._is_facundo_url(category_url):
        return self._original_category_pages(category_url, expected_count)

    return _facundo_category_pages(
        self,
        category_url,
        category_id,
        first_html,
        expected_count,
    )


def activate() -> None:
    """Install the fixes after the existing category pagination patch."""
    if not hasattr(CategoryScraper, "_original_category_pages"):
        CategoryScraper._original_category_pages = CategoryScraper.get_category_pages
    CategoryScraper.get_category_pages = _get_category_pages
    ProductExtractor._normalize_code_candidate = classmethod(_normalize_code_candidate)


activate()
