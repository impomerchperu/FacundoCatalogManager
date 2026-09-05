"""Recover first JetSmartFilters page through the original request path."""

from __future__ import annotations

from . import category_pagination_patch
from .category_scraper import CategoryScraper

JSF_PAGE_RETRIES = category_pagination_patch.JSF_PAGE_RETRIES
_browser_compatible_jsf_payload = category_pagination_patch._browser_compatible_jsf_payload
_remember_jsf_metadata = category_pagination_patch._remember_jsf_metadata


def _retry_first_page(
    self: CategoryScraper,
    category_url: str,
    category_id: int,
    page: int,
):
    """Fetch the first JSF page directly, with no competing method wrappers."""
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


category_pagination_patch._retry_jsf_page = _retry_first_page
CategoryScraper._fetch_jsf_page = _retry_first_page

__all__ = ["JSF_PAGE_RETRIES", "_retry_first_page"]
