"""Reliable pagination compatibility layer for category archives."""

import re

from .category_scraper import CategoryScraper

_PATCHED = False
_ORIGINAL_GET_CATEGORY_PAGES = CategoryScraper.get_category_pages
_PRODUCTS_IN_ARCHIVE_PATTERN = re.compile(
    r"Productos\s+en\s+Stock\s*[:\-]?\s*([\d\s.,]+)",
    re.IGNORECASE,
)


def pages_required(expected_count: int, products_per_page: int = 25) -> int:
    """Return the minimum number of pages required by a category count."""
    count = max(int(expected_count or 0), 0)
    per_page = max(int(products_per_page or 25), 1)
    return 0 if count == 0 else (count + per_page - 1) // per_page


def _published_product_count(html: str) -> int:
    """Read the archive's own category total, when it is published."""
    match = _PRODUCTS_IN_ARCHIVE_PATTERN.search(html or "")
    if not match:
        return 0
    try:
        return int(re.sub(r"\D", "", match.group(1)))
    except (TypeError, ValueError):
        return 0


def _safe_get_html(scraper: CategoryScraper, url: str) -> str:
    try:
        return scraper.get_html(url)
    except (AttributeError, RuntimeError, TypeError, ValueError):
        return ""


def _page_product_keys(scraper: CategoryScraper, html: str) -> set[str]:
    if not html:
        return set()
    try:
        return set(scraper._product_keys(html))
    except (AttributeError, TypeError, ValueError):
        return set()


def _facundo_jsf_pages(  # noqa: PLR0912
    scraper: CategoryScraper,
    category_url: str,
    category_id: int,
    first_html: str,
    expected_count: int,
) -> list[str]:
    """Discover every category page using public and JSF-local evidence."""
    pages = [category_url]
    scraper._cache_category_html(category_url, first_html)
    seen_products = _page_product_keys(scraper, first_html)

    published_count = _published_product_count(first_html)
    target_count = max(int(expected_count or 0), published_count)
    declared_pages = pages_required(target_count, scraper.PRODUCTS_PER_PAGE)

    jsf_page_one_available = True
    try:
        found_posts, jsf_max_pages, jsf_first_html = scraper._fetch_jsf_page(
            category_url, category_id, 1
        )
    except KeyError:
        jsf_page_one_available = False
        found_posts, jsf_max_pages, jsf_first_html = 0, 0, ""
    except (RuntimeError, TypeError, ValueError):
        found_posts, jsf_max_pages, jsf_first_html = 0, 0, ""

    target_count = max(target_count, found_posts)
    if jsf_page_one_available and found_posts > 0 and not jsf_first_html:
        raise RuntimeError(
            "JetSmartFilters no devolvió contenido para "
            f"{category_url} en la página 1."
        )
    if jsf_first_html:
        seen_products.update(_page_product_keys(scraper, jsf_first_html))
        scraper._cache_category_html(category_url, jsf_first_html)

    required_pages = max(
        declared_pages,
        pages_required(target_count, scraper.PRODUCTS_PER_PAGE),
        jsf_max_pages,
    )
    if expected_count > 0:
        required_pages = min(required_pages, declared_pages)

    hidden_page_probe = not jsf_page_one_available or jsf_max_pages <= 0
    next_page = 2
    probe_limit = max(required_pages, 2 if hidden_page_probe else 1)
    if expected_count > 0:
        probe_limit = min(
            probe_limit, pages_required(expected_count, scraper.PRODUCTS_PER_PAGE)
        )
    while next_page <= probe_limit:
        page_url = scraper._jsf_page_url(category_url, next_page)
        try:
            found_posts, jsf_max_pages, rendered_html = scraper._fetch_jsf_page(
                category_url, category_id, next_page
            )
        except (KeyError, RuntimeError, TypeError, ValueError):
            if next_page <= required_pages and len(seen_products) < target_count:
                raise RuntimeError(
                    "JetSmartFilters no devolvió contenido para "
                    f"{category_url} en la página {next_page}."
                ) from None
            break
        if not rendered_html:
            if next_page <= required_pages and len(seen_products) < target_count:
                raise RuntimeError(
                    "JetSmartFilters no devolvió contenido para "
                    f"{category_url} en la página {next_page}."
                )
            break

        scraper._cache_category_html(page_url, rendered_html)
        pages.append(page_url)
        page_keys = _page_product_keys(scraper, rendered_html)
        seen_products.update(page_keys)
        target_count = max(target_count, found_posts)
        required_pages = max(
            required_pages,
            jsf_max_pages,
            pages_required(target_count, scraper.PRODUCTS_PER_PAGE),
        )
        if expected_count > 0:
            required_pages = min(
                required_pages,
                pages_required(expected_count, scraper.PRODUCTS_PER_PAGE),
            )
        probe_limit = max(probe_limit, required_pages)
        if expected_count > 0:
            probe_limit = min(
                probe_limit,
                pages_required(expected_count, scraper.PRODUCTS_PER_PAGE),
            )

        if hidden_page_probe and jsf_max_pages <= 0 and len(page_keys) >= scraper.PRODUCTS_PER_PAGE:
            probe_limit = min(
                max(probe_limit, next_page + 1),
                next_page + scraper.MAX_HIDDEN_PAGE_PROBES,
            )
            if expected_count > 0:
                probe_limit = min(
                    probe_limit,
                    pages_required(expected_count, scraper.PRODUCTS_PER_PAGE),
                )
        next_page += 1

    return pages


def _generic_complete_pages(
    scraper: CategoryScraper,
    category_url: str,
    pages: list[str],
    expected_count: int,
) -> list[str]:
    """Continue public pagination until the category product coverage is met."""
    if not pages:
        return pages

    required_pages = pages_required(expected_count, scraper.PRODUCTS_PER_PAGE)
    if required_pages:
        pages = [
            page_url
            for page_url in pages
            if page_url == category_url
            or (
                (page_number := scraper._page_number(page_url)) is not None
                and page_number <= required_pages
            )
        ]

    seen_products: set[str] = set()
    first_html = ""
    for index, page_url in enumerate(pages):
        html = _safe_get_html(scraper, page_url)
        if index == 0:
            first_html = html
        seen_products.update(_page_product_keys(scraper, html))

    target_count = max(
        int(expected_count or 0), _published_product_count(first_html)
    )
    if target_count == 0:
        return pages

    next_page = max((scraper._page_number(url) or 1 for url in pages), default=1) + 1
    visited = set(pages)
    while len(seen_products) < target_count:
        if required_pages and next_page > required_pages:
            break
        page_url = scraper._fallback_page_url(category_url, next_page)
        if page_url in visited:
            next_page += 1
            continue
        html = _safe_get_html(scraper, page_url)
        page_keys = _page_product_keys(scraper, html)
        new_keys = page_keys.difference(seen_products)
        if not html or not new_keys:
            break
        seen_products.update(new_keys)
        scraper._cache_category_html(page_url, html)
        pages.append(page_url)
        visited.add(page_url)
        next_page += 1
    return pages


def _get_category_pages(
    self: CategoryScraper, category_url: str, expected_count: int = 0
) -> list[str]:
    """Discover archive pages using category-local evidence only."""
    first_html = _safe_get_html(self, category_url)
    if not first_html:
        return []
    category_id = self._category_id(first_html)
    if category_id is not None and self._is_facundo_url(category_url):
        return _facundo_jsf_pages(
            self, category_url, category_id, first_html, expected_count
        )

    self._cache_category_html(category_url, first_html)
    pages = _ORIGINAL_GET_CATEGORY_PAGES(
        self, category_url, expected_count=expected_count
    )
    return _generic_complete_pages(self, category_url, pages, expected_count)


def activate() -> None:
    """Install the compatibility behavior once for the collectors package."""
    global _PATCHED
    if not _PATCHED:
        CategoryScraper.get_category_pages = _get_category_pages
        _PATCHED = True


activate()

__all__ = ["CategoryScraper", "activate", "pages_required"]
