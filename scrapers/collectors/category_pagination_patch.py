"""Reliable pagination compatibility layer for category archives."""

import re

from .category_scraper import CategoryScraper

_PATCHED = False
_ORIGINAL_GET_CATEGORY_PAGES = CategoryScraper.get_category_pages
_PRODUCT_URL_PATTERN = re.compile(
    r'href=["\']([^"\']*/producto/[^"\'#?]+/?)[^"\']*["\']', re.IGNORECASE
)


def pages_required(expected_count: int, products_per_page: int = 25) -> int:
    """Return only a coverage estimate; never use it as a pagination ceiling."""
    count = max(int(expected_count or 0), 0)
    per_page = max(int(products_per_page or 25), 1)
    return 0 if count == 0 else (count + per_page - 1) // per_page


def _safe_get_html(scraper: CategoryScraper, url: str) -> str:
    try:
        return scraper.get_html(url)
    except (AttributeError, RuntimeError, TypeError, ValueError):
        return ""


def _is_real_product_html(html: str) -> bool:
    """Return whether HTML exposes actual product URLs used for probing."""
    return bool(_PRODUCT_URL_PATTERN.search(html or ""))


def _facundo_jsf_pages(
    scraper: CategoryScraper,
    category_url: str,
    category_id: int,
    first_html: str,
    expected_count: int,
) -> list[str]:
    """Fetch consecutive JSF pages without trusting incomplete metadata."""
    pages = [category_url]
    scraper._cache_category_html(category_url, first_html)

    try:
        found_posts, declared_pages, jsf_first_html = scraper._fetch_jsf_page(
            category_url, category_id, 1
        )
    except (KeyError, RuntimeError, TypeError, ValueError):
        found_posts, declared_pages, jsf_first_html = 0, 0, ""

    if jsf_first_html:
        scraper._cache_category_html(category_url, jsf_first_html)

    page = 2
    previous_html = jsf_first_html
    expected_pages = max(pages_required(expected_count), pages_required(found_posts))
    safety_limit = max(declared_pages or 0, expected_pages, 1)
    real_product_html = _is_real_product_html(jsf_first_html)

    while page <= safety_limit:
        page_url = scraper._jsf_page_url(category_url, page)
        try:
            _, page_count, rendered_html = scraper._fetch_jsf_page(
                category_url, category_id, page
            )
        except (KeyError, RuntimeError, TypeError, ValueError):
            break

        safety_limit = max(safety_limit, page_count)
        if not rendered_html or rendered_html == previous_html:
            break

        real_product_html = real_product_html or _is_real_product_html(rendered_html)
        scraper._cache_category_html(page_url, rendered_html)
        pages.append(page_url)
        previous_html = rendered_html
        page += 1

        # Only real product-bearing responses justify probing beyond metadata.
        if real_product_html and page > safety_limit:
            safety_limit = page + scraper.MAX_HIDDEN_PAGE_PROBES

    # Pagination is responsible for discovering pages, not proving product-count
    # coverage. The integration sync layer validates category/product coverage using
    # the complete set of discovered products.
    return pages


def _get_category_pages(
    self: CategoryScraper, category_url: str, expected_count: int = 0
) -> list[str]:
    """Discover every archive page using page content as the source of truth."""
    first_html = _safe_get_html(self, category_url)
    if not first_html:
        return []
    category_id = self._category_id(first_html)
    if category_id is not None and self._is_facundo_url(category_url):
        return _facundo_jsf_pages(
            self, category_url, category_id, first_html, expected_count
        )

    self._cache_category_html(category_url, first_html)
    return _ORIGINAL_GET_CATEGORY_PAGES(self, category_url, expected_count=0)


def activate() -> None:
    """Install the compatibility behavior once for the collectors package."""
    global _PATCHED
    if not _PATCHED:
        CategoryScraper.get_category_pages = _get_category_pages
        _PATCHED = True


activate()

__all__ = ["CategoryScraper", "activate", "pages_required"]
