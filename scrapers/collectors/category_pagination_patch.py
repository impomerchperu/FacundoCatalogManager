"""Reliable pagination compatibility layer for Facundo category archives."""

from __future__ import annotations

import json
import re
from threading import RLock
from urllib.parse import urljoin

from .category_scraper import CategoryScraper

_PATCHED = False
_ORIGINAL_GET_CATEGORY_PAGES = CategoryScraper.get_category_pages
_ORIGINAL_FETCH_JSF_PAGE = CategoryScraper._fetch_jsf_page
_ORIGINAL_JSF_PAYLOAD = CategoryScraper._jet_smart_filters_payload
_PRODUCT_URL_PATTERN = re.compile(
    r'href=["\']([^"\']*/producto/[^"\'#?]+/?)[^"\']*["\']', re.IGNORECASE
)
_JSF_SETTINGS_PATTERN = re.compile(
    r"var\s+JetSmartFilterSettings\s*=\s*(\{.*?\})\s*;", re.DOTALL
)
JSF_PAGE_RETRIES = 3
_JSF_STATE_LOCK = RLock()
_JSF_QUERY_STATE: dict[int, tuple[int, int]] = {}
_JSF_REQUEST_STATE: dict[int, dict[str, object]] = {}


def pages_required(expected_count: int, products_per_page: int = 25) -> int:
    """Return a coverage estimate; it is never a hard pagination ceiling."""
    count = max(int(expected_count or 0), 0)
    per_page = max(int(products_per_page or 25), 1)
    return 0 if count == 0 else (count + per_page - 1) // per_page


def _safe_get_html(scraper: CategoryScraper, url: str) -> str:
    try:
        return scraper.get_html(url)
    except (AttributeError, RuntimeError, TypeError, ValueError):
        return ""


def _direct_product_urls(html: str, base_url: str) -> set[str]:
    urls: set[str] = set()
    for raw_url in _PRODUCT_URL_PATTERN.findall(html or ""):
        absolute = urljoin(base_url.rstrip("/") + "/", raw_url)
        normalized = absolute.rstrip("/")
        if "/producto/" in normalized.casefold():
            urls.add(normalized.casefold())
    return urls


def _page_product_keys(
    self: CategoryScraper, html: str, base_url: str
) -> set[str]:
    """Return stable product identifiers from URLs/SKUs or page content."""
    return _direct_product_urls(html, base_url) | self._product_keys(html)


def _facundo_direct_pages(
    scraper: CategoryScraper,
    category_url: str,
    first_html: str,
    expected_count: int,
) -> tuple[list[str], int]:
    """Collect public archive pages as a compatibility fallback."""
    pages = scraper._fallback_category_pages(category_url, first_html, expected_count)
    product_urls: set[str] = set(_direct_product_urls(first_html, category_url))
    for page_url in pages[1:]:
        html = scraper._category_html_cache.get(page_url, "")
        if html:
            product_urls.update(_direct_product_urls(html, page_url))
    return pages, len(product_urls)


def _remember_jsf_settings(category_id: int, category_html: str) -> None:
    """Remember the live querydesk settings emitted by Facundo's page."""
    match = _JSF_SETTINGS_PATTERN.search(category_html or "")
    if not match:
        return
    try:
        settings = json.loads(match.group(1))
    except (TypeError, ValueError, json.JSONDecodeError):
        return
    try:
        query = settings["queries"]["bricks-query-loop"]["querydesk"]["query"]
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


def _remember_jsf_metadata(
    category_id: int, found_posts: int, max_num_pages: int
) -> None:
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
    if isinstance(orderby, dict) and orderby.get("menu_order"):
        values["defaults[orderby][menu_order]"] = str(orderby["menu_order"])
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


def _browser_compatible_jsf_payload(
    category_id: int, page: int
) -> list[tuple[str, str]]:
    """Build the smallest JSF request compatible with the live querydesk state."""
    with _JSF_STATE_LOCK:
        request_state = dict(_JSF_REQUEST_STATE.get(category_id, {}))
    payload = _ORIGINAL_JSF_PAYLOAD(category_id, 1)
    values = dict(payload)
    _apply_live_query_defaults(values, request_state.get("query"))
    _apply_live_request_settings(values, request_state.get("settings"))
    values["defaults[paged]"] = "1"
    values["props[page]"] = "1"
    values["paged"] = str(page)
    return [
        (key, values.get(key, value))
        for key, value in payload
        if key != "indexing_filters[]"
    ]


def _retry_jsf_page(
    self: CategoryScraper, category_url: str, category_id: int, page: int
):
    """Retry transport errors and empty JSF responses up to three total attempts."""
    last_error: Exception | None = None
    result = (0, 0, "")
    for _ in range(JSF_PAGE_RETRIES):
        try:
            cache_key = (category_url, page)
            with self._jsf_cache_lock:
                cached_html = self._jsf_page_cache.get(cache_key)
                cached_metadata = self._jsf_metadata_cache.get(category_url)
            if cached_html is not None:
                found_posts, max_num_pages = cached_metadata or (0, 0)
                return found_posts, max_num_pages, cached_html
            response_text = self._post_jsf(
                _browser_compatible_jsf_payload(category_id, page)
            )
            found_posts, max_num_pages, rendered_html = self._parse_jsf_response(
                response_text
            )
            _remember_jsf_metadata(category_id, found_posts, max_num_pages)
            if found_posts > 0 or max_num_pages > 0:
                with self._jsf_cache_lock:
                    self._jsf_metadata_cache[category_url] = (
                        found_posts,
                        max_num_pages,
                    )
            if rendered_html:
                with self._jsf_cache_lock:
                    self._jsf_page_cache[cache_key] = rendered_html
            result = (found_posts, max_num_pages, rendered_html)
        except (RuntimeError, TypeError, ValueError) as error:
            last_error = error
            continue
        if result[2] or result[0] > 0 or result[1] > 0:
            return result
    if last_error is not None:
        raise last_error
    return result


def _walk_jsf_page(
    self: CategoryScraper, category_url: str, category_id: int, page: int
):
    """Fetch one pagination page with exactly three total attempts."""
    fetcher = _ORIGINAL_FETCH_JSF_PAGE.__get__(self, CategoryScraper)
    last_error: Exception | None = None
    result = (0, 0, "")
    for _ in range(JSF_PAGE_RETRIES):
        try:
            result = fetcher(category_url, category_id, page)
        except (RuntimeError, TypeError, ValueError) as error:
            last_error = error
            continue
        if result[2]:
            return result
    if last_error is not None and not result[2]:
        raise last_error
    return result


def _probe_jsf_page(
    self: CategoryScraper, category_url: str, category_id: int, page: int
):
    """Probe a page once without adding retry layers."""
    fetcher = self._fetch_jsf_page
    if getattr(fetcher, "__func__", None) is _retry_jsf_page:
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


def _jsf_category_pages_with_probe(
    self: CategoryScraper,
    category_url: str,
    category_id: int,
    expected_count: int,
    category_html: str = "",
) -> list[str]:
    """Walk known JSF pages and validate the boundary without over-probing."""
    _remember_jsf_settings(category_id, category_html)
    found_posts, declared_max, first_html = _walk_jsf_page(
        self, category_url, category_id, 1
    )
    if not first_html:
        return [category_url]
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
    pages = [category_url]
    seen_product_keys = _page_product_keys(self, first_html, category_url)
    self._cache_category_html(category_url, category_html)
    for page_number in range(2, known_pages + 1):
        page_url = self._jsf_page_url(category_url, page_number)
        _, _, rendered_html = _walk_jsf_page(
            self, category_url, category_id, page_number
        )
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
    if known_pages > 1:
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
    for offset in range(min(self.MAX_HIDDEN_PAGE_PROBES, 5)):
        page_number = known_pages + offset + 1
        page_url = self._jsf_page_url(category_url, page_number)
        _, _, rendered_html = _probe_jsf_page(
            self, category_url, category_id, page_number
        )
        if not rendered_html:
            break
        current_product_keys = _page_product_keys(self, rendered_html, page_url)
        if not current_product_keys:
            break
        new_product_keys = current_product_keys - seen_product_keys
        if not new_product_keys:
            break
        seen_product_keys.update(current_product_keys)
        self._cache_category_html(page_url, rendered_html)
        pages.append(page_url)
    return pages


def _get_category_pages(
    self: CategoryScraper, category_url: str, expected_count: int = 0
) -> list[str]:
    """Use authoritative JSF pagination for Facundo and public fallback elsewhere."""
    first_html = _safe_get_html(self, category_url)
    if not first_html:
        return []
    if not self._is_facundo_url(category_url):
        self._cache_category_html(category_url, first_html)
        return _ORIGINAL_GET_CATEGORY_PAGES(
            self, category_url, expected_count=expected_count
        )
    category_id = self._category_id(first_html)
    if category_id is not None:
        self._cache_category_html(category_url, first_html)
        return _jsf_category_pages_with_probe(
            self,
            category_url,
            category_id,
            expected_count,
            category_html=first_html,
        )
    direct_products = _direct_product_urls(first_html, category_url)
    if direct_products:
        direct_pages, direct_count = _facundo_direct_pages(
            self, category_url, first_html, expected_count
        )
        expected = max(int(expected_count or 0), 0)
        if expected == 0 or direct_count >= expected:
            self._cache_category_html(category_url, first_html)
            return direct_pages
    self._cache_category_html(category_url, first_html)
    return _ORIGINAL_GET_CATEGORY_PAGES(
        self, category_url, expected_count=expected_count
    )


def activate() -> None:
    """Install the compatibility behavior once for the collectors package."""
    global _PATCHED
    if not _PATCHED:
        CategoryScraper._original_get_category_pages = _ORIGINAL_GET_CATEGORY_PAGES
        CategoryScraper._original_fetch_jsf_page = _ORIGINAL_FETCH_JSF_PAGE
        CategoryScraper._fetch_jsf_page = _retry_jsf_page
        CategoryScraper._jet_smart_filters_payload = staticmethod(
            _browser_compatible_jsf_payload
        )
        CategoryScraper.get_category_pages = _get_category_pages
        _PATCHED = True


activate()

__all__ = ["JSF_PAGE_RETRIES", "activate", "pages_required"]
