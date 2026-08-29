import contextlib
import json
import re
from threading import Lock
from typing import Any
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from config.scraping_config import (
    DEFAULT_HEADERS,
    JETSMARTFILTERS_AJAX_URL,
    JETSMARTFILTERS_ELEMENT_ID,
    JETSMARTFILTERS_INDEXING_FILTERS,
    JETSMARTFILTERS_SIGNATURE,
)


class CategoryScraper:
    """Scraper de categorías WooCommerce con paginación JetSmartFilters/Bricks."""

    PRODUCTS_PER_PAGE = 25
    MAX_HIDDEN_PAGE_PROBES = 100

    def __init__(
        self,
        browser: Any,
        parser: Any = None,
        category_extractor: Any = None,
        product_block_extractor: Any = None,
    ) -> None:
        self.parser = parser
        self.category_extractor = category_extractor
        self.product_block_extractor = product_block_extractor
        self.base_url: str | None = None
        self._category_html_cache: dict[str, str] = {}
        self._category_html_cache_lock = Lock()
        self._jsf_metadata_cache: dict[str, tuple[int, int]] = {}
        self._jsf_page_cache: dict[tuple[str, int], str] = {}
        self._jsf_cache_lock = Lock()
        if isinstance(browser, str):
            self.base_url = browser.rstrip("/")
            self.browser = None
        else:
            self.browser = browser

    def get_html(self, url: str) -> str:
        with self._category_html_cache_lock:
            cached_html = self._category_html_cache.pop(url, None)
        if cached_html is not None:
            return cached_html
        if self.browser:
            return self._response_text(self.browser.get(url))
        response = requests.get(url, timeout=20, headers=DEFAULT_HEADERS)
        response.raise_for_status()
        return response.text

    @staticmethod
    def _response_text(response: Any) -> str:
        if isinstance(response, str):
            return response
        text = getattr(response, "text", None)
        if isinstance(text, str):
            return text
        return str(response)

    def _cache_category_html(self, url: str, html: str) -> None:
        if html:
            with self._category_html_cache_lock:
                self._category_html_cache[url] = html

    def _parse(self, html: str) -> Any:
        if self.parser and hasattr(self.parser, "parse"):
            return self.parser.parse(html)
        return BeautifulSoup(html, "html.parser")

    def scrape(self, url: str) -> Any:
        html = self.get_html(url)
        if not html:
            return []
        if self.parser and hasattr(self.parser, "extract_categories"):
            return self.parser.extract_categories(html)
        soup = self._parse(html)
        if self.category_extractor:
            return self.category_extractor.extract(soup)
        return []

    def get_product_urls(self, url: str) -> Any:
        html = self.get_html(url)
        if not html:
            return []
        soup = self._parse(html)
        if self.category_extractor:
            return self.category_extractor.extract(soup)
        return []

    def get_category_pages(
        self, category_url: str, expected_count: int = 0
    ) -> list[str]:
        category_html = self.get_html(category_url)
        if not category_html:
            return []
        category_id = self._category_id(category_html)
        if category_id is not None and self._is_facundo_url(category_url):
            return self._jsf_category_pages(
                category_url, category_id, expected_count
            )
        return self._fallback_category_pages(
            category_url, category_html, expected_count
        )

    def _jsf_category_pages(
        self, category_url: str, category_id: int, expected_count: int
    ) -> list[str]:
        found_posts, max_num_pages, first_html = self._fetch_jsf_page(
            category_url, category_id, 1
        )
        category_total = max(int(expected_count or 0), found_posts)
        required_pages = (
            category_total + self.PRODUCTS_PER_PAGE - 1
        ) // self.PRODUCTS_PER_PAGE
        max_num_pages = max(
            max_num_pages,
            required_pages,
            self._declared_total_pages(first_html),
            self._pagination_max_page(first_html),
        )
        if expected_count > 0:
            max_num_pages = min(max_num_pages, required_pages)
        if max_num_pages <= 0:
            return [category_url]
        if not first_html:
            raise RuntimeError(
                "JetSmartFilters no devolvió contenido para "
                f"{category_url} en la página 1."
            )

        pages = [category_url]
        self._cache_category_html(category_url, first_html)
        for page_number in range(2, max_num_pages + 1):
            page_url = self._jsf_page_url(category_url, page_number)
            rendered_html = self._fetch_category_page_html(
                category_url, category_id, page_number, page_url
            )
            if not rendered_html:
                raise RuntimeError(
                    "JetSmartFilters no devolvió contenido para "
                    f"{category_url} en la página "
                    f"{page_number}/{max_num_pages}."
                )
            self._cache_category_html(page_url, rendered_html)
            pages.append(page_url)
        if len(pages) != max_num_pages:
            raise RuntimeError(
                f"Paginación incompleta para {category_url}: "
                f"{len(pages)}/{max_num_pages} páginas."
            )
        return pages

    def _fetch_category_page_html(
        self,
        category_url: str,
        category_id: int,
        page: int,
        page_url: str,
    ) -> str:
        """Obtiene contenido de página; Facundo usa JSF como fuente primaria."""
        if self._is_facundo_url(category_url):
            _, _, rendered_html = self._fetch_jsf_page(
                category_url, category_id, page
            )
            return rendered_html

        try:
            html = self.get_html(page_url)
        except requests.RequestException:
            html = ""
        if html and self._product_keys(html):
            return html
        _, _, rendered_html = self._fetch_jsf_page(
            category_url, category_id, page
        )
        return rendered_html or html

    def _fallback_category_pages(
        self, category_url: str, category_html: str, expected_count: int
    ) -> list[str]:
        pages = [category_url]
        discovered = self._fallback_pagination_links(
            category_url, category_html
        )
        required_pages = self._required_page_count(expected_count)
        if required_pages:
            discovered = self._limit_page_urls(discovered, required_pages)
        total_pages = self._determine_fallback_total_pages(
            category_html, discovered, required_pages
        )
        discovered = self._complete_page_sequence(
            category_url, discovered, total_pages
        )
        pages.extend(self._collect_fallback_pages(
            category_url, discovered, required_pages
        ))
        if total_pages == 0 and not discovered:
            visited = set(pages)
            self._probe_hidden_pages(
                category_url,
                pages,
                visited,
                start_page=2,
                max_page=required_pages or None,
            )
        if required_pages:
            pages = [
                pages[0],
                *[
                    url
                    for url in pages[1:]
                    if (page_number := self._page_number(url)) is not None
                    and page_number <= required_pages
                ],
            ]
        return pages

    def _required_page_count(self, expected_count: int) -> int:
        if expected_count <= 0:
            return 0
        return (
            expected_count + self.PRODUCTS_PER_PAGE - 1
        ) // self.PRODUCTS_PER_PAGE

    def _limit_page_urls(self, urls: list[str], max_page: int) -> list[str]:
        return [
            url
            for url in urls
            if (page_number := self._page_number(url)) is not None
            and page_number <= max_page
        ]

    def _determine_fallback_total_pages(
        self,
        category_html: str,
        discovered: list[str],
        required_pages: int,
    ) -> int:
        declared_total = self._declared_total_pages(category_html)
        discovered_total = self._pagination_max_page(category_html)
        total_pages = max(declared_total, discovered_total)
        if required_pages:
            return min(max(total_pages, required_pages), required_pages)
        return total_pages

    def _complete_page_sequence(
        self,
        category_url: str,
        discovered: list[str],
        total_pages: int,
    ) -> list[str]:
        numbers = {
            number
            for number in (self._page_number(url) for url in discovered)
            if number is not None
        }
        for page in range(2, total_pages + 1):
            if page not in numbers:
                discovered.append(self._fallback_page_url(category_url, page))
                numbers.add(page)
        return discovered

    def _collect_fallback_pages(
        self,
        category_url: str,
        discovered: list[str],
        required_pages: int,
    ) -> list[str]:
        pages: list[str] = []
        pending = list(discovered)
        visited = {category_url}
        while pending:
            page_url = pending.pop(0)
            if page_url in visited:
                continue
            page_number = self._page_number(page_url)
            if required_pages and (
                page_number is None or page_number > required_pages
            ):
                continue
            visited.add(page_url)
            pages.append(page_url)
            html = self.get_html(page_url)
            if not html:
                continue
            self._cache_category_html(page_url, html)
            for next_url in self._fallback_pagination_links(
                category_url, html
            ):
                if next_url in visited or next_url in pending:
                    continue
                next_number = self._page_number(next_url)
                if required_pages and (
                    next_number is None or next_number > required_pages
                ):
                    continue
                pending.append(next_url)
        return pages

    def _probe_hidden_pages(
        self,
        category_url: str,
        pages: list[str],
        visited: set[str],
        start_page: int,
        max_page: int | None = None,
    ) -> None:
        """Recupera páginas consecutivas cuando la paginación no se publica."""
        probe_limit = self.MAX_HIDDEN_PAGE_PROBES
        if max_page is not None:
            probe_limit = min(probe_limit, max_page - start_page + 1)
        if probe_limit <= 0:
            return
        for offset in range(probe_limit):
            page = start_page + offset
            page_url = self._fallback_page_url(category_url, page)
            if page_url in visited:
                continue
            html = self.get_html(page_url)
            if not html or not self._product_keys(html):
                break
            visited.add(page_url)
            pages.append(page_url)
            self._cache_category_html(page_url, html)
            self._append_valid_pagination_links(
                category_url, html, pages, visited, page
            )

    def _append_valid_pagination_links(
        self,
        category_url: str,
        html: str,
        pages: list[str],
        visited: set[str],
        current_page: int,
    ) -> None:
        for next_url in self._fallback_pagination_links(
            category_url, html
        ):
            if next_url in visited:
                continue
            page_number = self._page_number(next_url)
            if page_number is None or page_number <= current_page:
                continue
            pages.append(next_url)
            visited.add(next_url)

    @staticmethod
    def _product_keys(html: str) -> set[str]:
        keys = set(
            re.findall(
                r"\b[A-Z]{2,}[A-Z0-9]*(?:-[A-Z0-9]+)+\b",
                html or "",
            )
        )
        return keys
