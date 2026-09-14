"""Canonical pagination engine for Facundo category archives."""

from __future__ import annotations

import json
import re
from threading import RLock
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from .category_scraper import CategoryScraper

JSF_PAGE_RETRIES = 3
_JSF_SETTINGS_PATTERN = re.compile(
    r"var\s+JetSmartFilterSettings\s*=\s*(\{.*?\})\s*;",
    re.DOTALL,
)
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
    scraper: CategoryScraper,
    html: str,
    base_url: str,
) -> set[str]:
    """Prefer real product URLs; fall back to explicit product-code keys."""
    product_urls = _direct_product_urls(html, base_url)
    if product_urls:
        return product_urls
    return scraper._product_keys(html)


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
    """Build the browser-compatible JSF payload used successfully by the site."""
    with _JSF_STATE_LOCK:
        request_state = dict(_JSF_REQUEST_STATE.get(category_id, {}))

    payload = CategoryScraper._jet_smart_filters_payload(category_id, page)
    values = dict(payload)
    _apply_live_query_defaults(values, request_state.get("query"))
    _apply_live_request_settings(values, request_state.get("settings"))
    values["defaults[paged]"] = str(page)
    values["props[page]"] = str(page)
    values["paged"] = str(page)

    return [
        (key, values.get(key, value))
        for key, value in payload
        if key != "indexing_filters[]"
    ]


def _fetch_jsf_page_direct(
    scraper: CategoryScraper,
    category_url: str,
    category_id: int,
    page: int,
) -> tuple[int, int, str]:
    response_text = scraper._post_jsf(_browser_compatible_jsf_payload(category_id, page))
    found_posts, max_num_pages, rendered_html = scraper._parse_jsf_response(response_text)
    if found_posts > 0 or max_num_pages > 0:
        with scraper._jsf_cache_lock:
            scraper._jsf_metadata_cache[category_url] = (found_posts, max_num_pages)
    if rendered_html:
        with scraper._jsf_cache_lock:
            scraper._jsf_page_cache[(category_url, page)] = rendered_html
    return found_posts, max_num_pages, rendered_html


def _retry_jsf_page(
    scraper: CategoryScraper,
    category_url: str,
    category_id: int,
    page: int,
) -> tuple[int, int, str]:
    last_error: requests.RequestException | None = None
    result = (0, 0, "")
    for _ in range(JSF_PAGE_RETRIES):
        try:
            result = _fetch_jsf_page_direct(scraper, category_url, category_id, page)
        except requests.RequestException as error:
            last_error = error
            continue
        except (RuntimeError, TypeError, ValueError):
            raise
        if result[2]:
            return result
    if last_error is not None and not result[2]:
        raise last_error
    return result


def _walk_jsf_page(
    scraper: CategoryScraper,
    category_url: str,
    category_id: int,
    page: int,
) -> tuple[int, int, str]:
    return _retry_jsf_page(scraper, category_url, category_id, page)


def _probe_jsf_page(
    scraper: CategoryScraper,
    category_url: str,
    category_id: int,
    page: int,
) -> tuple[int, int, str]:
    return scraper._fetch_jsf_page(category_url, category_id, page)


def _probe_boundary_page(
    scraper: CategoryScraper,
    category_url: str,
    category_id: int,
    page: int,
    seen_product_keys: set[str],
) -> tuple[bool, set[str], int, int]:
    page_url = scraper._jsf_page_url(category_url, page)
    found_posts, max_num_pages, rendered_html = _probe_jsf_page(
        scraper,
        category_url,
        category_id,
        page,
    )
    if not rendered_html:
        return False, set(), found_posts, max_num_pages
    current_product_keys = _page_product_keys(scraper, rendered_html, page_url)
    if not current_product_keys:
        return False, set(), found_posts, max_num_pages
    new_product_keys = current_product_keys - seen_product_keys
    if not new_product_keys:
        return False, set(), found_posts, max_num_pages
    scraper._cache_category_html(page_url, rendered_html)
    return True, new_product_keys, found_posts, max_num_pages


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
    for candidate in _page_variants(category_url, page_number):
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
        html = _safe_get_html(scraper, page_url)
        if not html:
            continue
        current = _page_product_keys(scraper, html, page_url)
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
                f"No unique products found on public pagination page {page_number} for {category_url}"
            )
        pages.append(accepted_url)
        declared_pages = max(
            declared_pages,
            max(discovered_by_number, default=0),
        )

    return pages, seen


def _initial_jsf_page(
    scraper: CategoryScraper,
    category_url: str,
    category_id: int,
    category_html: str,
    use_archive_first_page: bool,
) -> tuple[int, int, str]:
    if use_archive_first_page:
        with _JSF_STATE_LOCK:
            found_posts, declared_max = _JSF_QUERY_STATE.get(category_id, (0, 0))
        return found_posts, declared_max, category_html
    return _retry_jsf_page(scraper, category_url, category_id, 1)


def _jsf_category_pages_with_probe(
    scraper: CategoryScraper,
    category_url: str,
    category_id: int,
    expected_count: int,
    category_html: str = "",
) -> list[str]:
    """Use authoritative JSF pagination with validated archive fast-path."""
    _remember_jsf_settings(category_id, category_html)
    archive_product_urls = _direct_product_urls(category_html, category_url)
    use_archive_first_page = bool(archive_product_urls) and len(archive_product_urls) <= scraper.PRODUCTS_PER_PAGE

    found_posts, declared_max, first_html = _initial_jsf_page(
        scraper,
        category_url,
        category_id,
        category_html,
        use_archive_first_page,
    )

    expected_pages = scraper._required_page_count(expected_count)
    published_pages = scraper._required_page_count(found_posts)
    response_html_pages = max(
        scraper._declared_total_pages(first_html),
        scraper._pagination_max_page(first_html),
    )
    category_html_pages = max(
        scraper._declared_total_pages(category_html),
        scraper._pagination_max_page(category_html),
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
    seen_product_keys = _page_product_keys(scraper, first_html, category_url)
    scraper._cache_category_html(category_url, category_html)
    if use_archive_first_page:
        with scraper._jsf_cache_lock:
            scraper._jsf_page_cache[(category_url, 1)] = first_html

    page_number = 2
    while page_number <= known_pages:
        page_url = scraper._jsf_page_url(category_url, page_number)
        page_found, page_max, rendered_html = _walk_jsf_page(
            scraper,
            category_url,
            category_id,
            page_number,
        )
        if not rendered_html:
            raise RuntimeError(
                f"Empty JSF pagination page {page_number} for {category_url}"
            )
        current_product_keys = _page_product_keys(scraper, rendered_html, page_url)
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
        scraper._cache_category_html(page_url, rendered_html)
        pages.append(page_url)
        known_pages = max(
            known_pages,
            scraper._required_page_count(page_found),
            page_max,
            scraper._declared_total_pages(rendered_html),
            scraper._pagination_max_page(rendered_html),
        )
        page_number += 1

    boundary_page = known_pages + 1
    has_new_products, new_product_keys, boundary_found, boundary_max = _probe_boundary_page(
        scraper,
        category_url,
        category_id,
        boundary_page,
        seen_product_keys,
    )
    if has_new_products:
        seen_product_keys.update(new_product_keys)
        pages.append(scraper._jsf_page_url(category_url, boundary_page))
        known_pages = max(
            known_pages,
            boundary_max,
            scraper._required_page_count(boundary_found),
        )
        page_number = boundary_page + 1
        while page_number <= known_pages:
            page_url = scraper._jsf_page_url(category_url, page_number)
            page_found, page_max, rendered_html = _walk_jsf_page(
                scraper,
                category_url,
                category_id,
                page_number,
            )
            if not rendered_html:
                raise RuntimeError(
                    f"Empty JSF pagination page {page_number} for {category_url}"
                )
            current_product_keys = _page_product_keys(scraper, rendered_html, page_url)
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
            scraper._cache_category_html(page_url, rendered_html)
            pages.append(page_url)
            known_pages = max(
                known_pages,
                scraper._required_page_count(page_found),
                page_max,
                scraper._declared_total_pages(rendered_html),
                scraper._pagination_max_page(rendered_html),
            )
            page_number += 1
    return pages


def get_category_pages(
    scraper: CategoryScraper,
    category_url: str,
    expected_count: int = 0,
) -> list[str]:
    """Use authoritative JSF pagination for Facundo with validated public fallback."""
    first_html = _safe_get_html(scraper, category_url)
    if not first_html:
        return []

    if not scraper._is_facundo_url(category_url):
        scraper._cache_category_html(category_url, first_html)
        return scraper._fallback_category_pages(
            category_url,
            first_html,
            expected_count,
        )

    category_id = scraper._category_id(first_html)
    if category_id is not None:
        scraper._cache_category_html(category_url, first_html)
        return _jsf_category_pages_with_probe(
            scraper,
            category_url,
            category_id,
            expected_count,
            category_html=first_html,
        )

    direct_products = _direct_product_urls(first_html, category_url)
    if direct_products:
        try:
            pages, seen = _collect_direct_pages(
                scraper,
                category_url,
                first_html,
                expected_count,
            )
        except RuntimeError:
            pages, seen = [category_url], direct_products

        target = max(int(expected_count or 0), 0)
        if target == 0 or len(seen) >= target:
            scraper._cache_category_html(category_url, first_html)
            return pages

    scraper._cache_category_html(category_url, first_html)
    return scraper._fallback_category_pages(
        category_url,
        first_html,
        expected_count,
    )


__all__ = [
    "JSF_PAGE_RETRIES",
    "_collect_direct_pages",
    "_direct_product_urls",
    "_jsf_category_pages_with_probe",
    "_page_product_keys",
    "get_category_pages",
    "pages_required",
]
