"""Reliable pagination compatibility layer for Facundo category archives."""

from __future__ import annotations

import json
import re
from threading import RLock
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .category_scraper import CategoryScraper

_PATCHED = False
_ORIGINAL_GET_CATEGORY_PAGES = CategoryScraper.get_category_pages
_ORIGINAL_FETCH_JSF_PAGE = CategoryScraper._fetch_jsf_page
_ORIGINAL_JSF_PAYLOAD = CategoryScraper._jet_smart_filters_payload
_JSF_SETTINGS_PATTERN = re.compile(
    r"var\s+JetSmartFilterSettings\s*=\s*(\{.*?\})\s*;",
    re.DOTALL,
)
JSF_PAGE_RETRIES = 3
_JSF_STATE_LOCK = RLock()
_JSF_QUERY_STATE: dict[int, tuple[int, int]] = {}
_JSF_REQUEST_STATE: dict[int, dict[str, object]] = {}


def pages_required(expected_count: int, products_per_page: int = 25) -> int:
    """Return the minimum number of pages required for a coverage target."""
    count = max(int(expected_count or 0), 0)
    per_page = max(int(products_per_page or 25), 1)
    return 0 if count == 0 else (count + per_page - 1) // per_page


def _safe_get_html(scraper: CategoryScraper, url: str) -> str:
    try:
        return scraper.get_html(url)
    except (AttributeError, RuntimeError, TypeError, ValueError):
        return ""


def _direct_product_urls(html: str, base_url: str) -> set[str]:
    """Extract normalized product URLs from category HTML."""
    soup = BeautifulSoup(html or "", "html.parser")
    urls: set[str] = set()
    for link in soup.select('a[href*="/producto/"]'):
        href = link.get("href")
        if not isinstance(href, str) or not href.strip():
            continue
        absolute = urljoin(base_url, href.strip())
        normalized = absolute.rstrip("/").casefold()
        if "/producto/" in normalized:
            urls.add(normalized)
    return urls


def _page_product_keys(
    self: CategoryScraper,
    html: str,
    base_url: str,
) -> set[str]:
    """Prefer explicit product codes; use URLs only when codes are absent."""
    code_keys = self._product_keys(html)
    if code_keys:
        return code_keys
    return _direct_product_urls(html, base_url)


def _page_variants(category_url: str, page: int) -> list[str]:
    """Return public pagination variants while preserving the archive slash."""
    archive_url = category_url.split("?", 1)[0].rstrip("/")
    return [
        f"{archive_url}/page/{page}/",
        f"{archive_url}/?product-page={page}",
        f"{archive_url}/?paged={page}",
    ]


def _remember_jsf_settings(category_id: int, category_html: str) -> None:
    """Remember live querydesk settings emitted by Facundo's page."""
    match = _JSF_SETTINGS_PATTERN.search(category_html or "")
    if not match:
        with _JSF_STATE_LOCK:
            _JSF_REQUEST_STATE.pop(category_id, None)
        return
    try:
        settings = json.loads(match.group(1))
    except (TypeError, ValueError, json.JSONDecodeError):
        return
    try:
        query = settings["queries"]["bricks-query-loop"]["querydesk"]
        request_settings = settings["settings"]["bricks-query-loop"]["querydesk"]
    except (KeyError, TypeError):
        return
    if not isinstance(query, dict) or not isinstance(request_settings, dict):
        return
    with _JSF_STATE_LOCK:
        _JSF_REQUEST_STATE[category_id] = {
            "query": dict(query),
            "settings": dict(request_settings),
        }
    props = settings.get("props", {})
    try:
        query_props = props["bricks-query-loop"]["querydesk"]
    except (KeyError, TypeError):
        query_props = {}
    if isinstance(query_props, dict):
        _remember_jsf_metadata(
            category_id,
            CategoryScraper._to_int(query_props.get("found_posts")),
            CategoryScraper._to_int(query_props.get("max_num_pages")),
        )


def _remember_jsf_metadata(category_id: int, found_posts: int, max_num_pages: int) -> None:
    if found_posts <= 0 and max_num_pages <= 0:
        return
    with _JSF_STATE_LOCK:
        _JSF_QUERY_STATE[category_id] = (found_posts, max_num_pages)


def _apply_live_query_defaults(values: dict[str, str], query: object) -> None:
    if not isinstance(query, dict):
        return
    post_type = query.get("post_type")
    if isinstance(post_type, list) and post_type:
        values["defaults[post_type][]"] = str(post_type[0])
    orderby = query.get("orderby")
    if isinstance(orderby, dict):
        menu_order = orderby.get("menu_order")
        if menu_order:
            values["defaults[orderby][menu_order]"] = str(menu_order)
    for key in (
        "posts_per_page",
        "no_results_text",
        "disable_query_merge",
        "is_archive_main_query",
        "post_status",
    ):
        value = query.get(key)
        if value is None:
            continue
        values[f"defaults[{key}]"] = (
            str(value).lower() if isinstance(value, bool) else str(value)
        )


def _apply_live_request_settings(values: dict[str, str], settings: object) -> None:
    if not isinstance(settings, dict):
        return
    filtered_post_id = settings.get("filtered_post_id")
    element_id = settings.get("element_id")
    archive_query = settings.get("is_archive_main_query")
    signature = settings.get("jsf_signature")
    if filtered_post_id is not None:
        values["query[_tax_query_product_cat]"] = str(filtered_post_id)
        values["settings[filtered_post_id]"] = str(filtered_post_id)
    if element_id:
        values["settings[element_id]"] = str(element_id)
    if archive_query is not None:
        values["settings[is_archive_main_query]"] = str(archive_query).lower()
    if signature:
        values["settings[jsf_signature]"] = str(signature)


def _browser_compatible_jsf_payload(category_id: int, page: int) -> list[tuple[str, str]]:
    """Build a JSF payload compatible with the live browser request state."""
    with _JSF_STATE_LOCK:
        request_state = dict(_JSF_REQUEST_STATE.get(category_id, {}))
    if not request_state:
        return _ORIGINAL_JSF_PAYLOAD(category_id, page)
    payload = _ORIGINAL_JSF_PAYLOAD(category_id, page)
    values = dict(payload)
    _apply_live_query_defaults(values, request_state.get("query"))
    _apply_live_request_settings(values, request_state.get("settings"))
    values["defaults[paged]"] = str(page)
    values["props[page]"] = str(page)
    values["paged"] = str(page)
    return [(key, values.get(key, value)) for key, value in payload]


def _fetch_jsf_page_direct(
    self: CategoryScraper,
    category_url: str,
    category_id: int,
    page: int,
):
    response_text = self._post_jsf(_browser_compatible_jsf_payload(category_id, page))
    found_posts, max_num_pages, rendered_html = self._parse_jsf_response(response_text)
    if found_posts > 0 or max_num_pages > 0:
        with self._jsf_cache_lock:
            self._jsf_metadata_cache[category_url] = (found_posts, max_num_pages)
    if rendered_html:
        with self._jsf_cache_lock:
            self._jsf_page_cache[(category_url, page)] = rendered_html
    return found_posts, max_num_pages, rendered_html


def _retry_jsf_page(self: CategoryScraper, category_url: str, category_id: int, page: int):
    last_error: Exception | None = None
    result = (0, 0, "")
    for _ in range(JSF_PAGE_RETRIES):
        try:
            result = _fetch_jsf_page_direct(self, category_url, category_id, page)
        except (RuntimeError, TypeError, ValueError) as error:
            last_error = error
            continue
        if result[2]:
            return result
    if last_error is not None:
        raise last_error
    return result


def _walk_jsf_page(self: CategoryScraper, category_url: str, category_id: int, page: int):
    return _retry_jsf_page(self, category_url, category_id, page)


def _probe_jsf_page(self: CategoryScraper, category_url: str, category_id: int, page: int):
    fetcher = _ORIGINAL_FETCH_JSF_PAGE.__get__(self, CategoryScraper)
    return fetcher(category_url, category_id, page)


def _probe_boundary_page(
    self: CategoryScraper,
    category_url: str,
    category_id: int,
    page: int,
    seen_product_keys: set[str],
) -> tuple[bool, set[str]]:
    page_url = self._jsf_page_url(category_url, page)
    _, _, rendered_html = _probe_jsf_page(self, category_url, category_id, page)
    if not rendered_html:
        return False, set()
    current_product_keys = _page_product_keys(self, rendered_html, page_url)
    if not current_product_keys:
        return False, set()
    new_product_keys = current_product_keys - seen_product_keys
    if not new_product_keys:
        return False, set()
    self._cache_category_html(page_url, rendered_html)
    return True, new_product_keys


def _collect_direct_pages(
    scraper: CategoryScraper,
    category_url: str,
    first_html: str,
    expected_count: int,
) -> tuple[list[str], set[str]]:
    """Collect real public page links and validate their product sets."""
    expected_pages = pages_required(expected_count, scraper.PRODUCTS_PER_PAGE)
    initial_keys = _page_product_keys(scraper, first_html, category_url)
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
        candidates = []
        discovered_url = discovered_by_number.get(page_number)
        if discovered_url:
            candidates.append(discovered_url)
        for candidate in _page_variants(category_url, page_number):
            if candidate not in candidates:
                candidates.append(candidate)

        accepted = False
        for page_url in candidates:
            html = _safe_get_html(scraper, page_url)
            if not html:
                continue
            current = _page_product_keys(scraper, html, page_url)
            if not current:
                continue
            new_keys = current - seen
            if not new_keys:
                continue
            seen.update(current)
            scraper._cache_category_html(page_url, html)
            pages.append(page_url)
            accepted = True
            break

        if not accepted:
            raise RuntimeError(
                f"No unique products found on public pagination page "
                f"{page_number} for {category_url}"
            )

    return pages, seen


def _jsf_category_pages_with_probe(
    self: CategoryScraper,
    category_url: str,
    category_id: int,
    expected_count: int,
    category_html: str = "",
) -> list[str]:
    """Use JSF only as an authoritative source when public pagination cannot cover the target."""
    _remember_jsf_settings(category_id, category_html)
    found_posts, declared_max, first_html = _retry_jsf_page(self, category_url, category_id, 1)

    expected_pages = self._required_page_count(expected_count)
    published_pages = self._required_page_count(found_posts)
    response_html_pages = max(
        self._declared_total_pages(first_html),
        self._pagination_max_page(first_html),
    )
    category_html_pages = max(
        self._declared_total_pages(category_html),
        self._pagination_max_page(category_html),
    )
    known_pages = max(
        declared_max,
        published_pages,
        expected_pages,
        response_html_pages,
        category_html_pages,
        1,
    )

    if not first_html and known_pages <= 1:
        return [category_url]

    pages = [category_url]
    seen_product_keys = _page_product_keys(self, first_html, category_url)
    self._cache_category_html(category_url, category_html)

    for page_number in range(2, known_pages + 1):
        page_url = self._jsf_page_url(category_url, page_number)
        _, _, rendered_html = _walk_jsf_page(self, category_url, category_id, page_number)
        if not rendered_html:
            raise RuntimeError(
                f"Empty JSF pagination page {page_number} for {category_url}"
            )
        current_product_keys = _page_product_keys(self, rendered_html, page_url)
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
    has_new_products, new_product_keys = _probe_boundary_page(
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


def _get_category_pages(
    self: CategoryScraper,
    category_url: str,
    expected_count: int = 0,
) -> list[str]:
    """Prefer real public pagination; use JSF only when public coverage is insufficient."""
    first_html = _safe_get_html(self, category_url)
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

    if not self._is_facundo_url(category_url):
        if target > 0 and len(seen) >= target:
            return pages
        self._cache_category_html(category_url, first_html)
        return _ORIGINAL_GET_CATEGORY_PAGES(
            self,
            category_url,
            expected_count=expected_count,
        )

    category_id = self._category_id(first_html)
    if category_id is None:
        return pages

    if target > 0 and len(seen) >= target:
        return pages

    self._cache_category_html(category_url, first_html)
    return _jsf_category_pages_with_probe(
        self,
        category_url,
        category_id,
        expected_count,
        category_html=first_html,
    )


def activate() -> None:
    """Install the pagination compatibility patch once."""
    global _PATCHED
    if _PATCHED:
        return
    CategoryScraper.get_category_pages = _get_category_pages
    _PATCHED = True


activate()

__all__ = ["JSF_PAGE_RETRIES", "activate", "pages_required"]
