"""Runtime compatibility fixes for the Facundo catalog scraper."""

import re

from scrapers.extractors.product_extractor import ProductExtractor
from .category_scraper import CategoryScraper

_PRODUCT_URL_PATTERN = re.compile(
    r'href=["\']([^"\']*/producto/[^"\'#?]+/?)[^"\']*["\']',
    re.IGNORECASE,
)


def _normalize_code_candidate(cls, text: str) -> str:
    """Accept alphanumeric SKU codes with or without digits."""
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
    """Traverse every JSF page and continue until the server returns no new products."""
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

    page = 2
    hidden_probes = 0
    while hidden_probes < scraper.MAX_HIDDEN_PAGE_PROBES:
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
            break

        scraper._cache_category_html(page_url, page_html)
        pages.append(page_url)
        seen.update(current)
        page += 1

        if page > required:
            hidden_probes += 1
        else:
            hidden_probes = 0

    return pages


def _get_category_pages(self, category_url: str, expected_count: int = 0) -> list[str]:
    first_html = self.get_html(category_url)
    if not first_html:
        return []

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
