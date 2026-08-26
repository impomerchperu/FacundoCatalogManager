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

    def _fetch_jsf_page(
        self, category_url: str, category_id: int, page: int
    ) -> tuple[int, int, str]:
        cache_key = (category_url, page)
        with self._jsf_cache_lock:
            cached_html = self._jsf_page_cache.get(cache_key)
            cached_metadata = self._jsf_metadata_cache.get(category_url)
        if cached_html is not None:
            found_posts, max_num_pages = cached_metadata or (0, 0)
            return found_posts, max_num_pages, cached_html

        response_text = self._post_jsf(
            self._jet_smart_filters_payload(category_id, page)
        )
        found_posts, max_num_pages, rendered_html = self._parse_jsf_response(
            response_text
        )
        if found_posts > 0 or max_num_pages > 0:
            with self._jsf_cache_lock:
                self._jsf_metadata_cache[category_url] = (
                    found_posts,
                    max_num_pages,
                )
        if rendered_html:
            with self._jsf_cache_lock:
                self._jsf_page_cache[cache_key] = rendered_html
        return found_posts, max_num_pages, rendered_html

    def _post_jsf(self, payload: list[tuple[str, str]]) -> str:
        if self.browser and hasattr(self.browser, "post"):
            return self._response_text(
                self.browser.post(JETSMARTFILTERS_AJAX_URL, data=payload)
            )
        response = requests.post(
            JETSMARTFILTERS_AJAX_URL,
            data=payload,
            headers=DEFAULT_HEADERS,
            timeout=20,
        )
        response.raise_for_status()
        return response.text

    @staticmethod
    def _jet_smart_filters_payload(
        category_id: int, page: int
    ) -> list[tuple[str, str]]:
        return [
            ("action", "jet_smart_filters"),
            ("provider", "bricks-query-loop/querydesk"),
            ("query[_tax_query_product_cat]", str(category_id)),
            ("defaults[post_type][]", "product"),
            ("defaults[orderby][menu_order]", "ASC"),
            ("defaults[posts_per_page]", "25"),
            ("defaults[no_results_text]", "No existen productos"),
            ("defaults[disable_query_merge]", "true"),
            ("defaults[is_archive_main_query]", "true"),
            ("defaults[post_status]", "publish"),
            ("defaults[paged]", str(page)),
            ("settings[filtered_post_id]", str(category_id)),
            ("settings[element_id]", JETSMARTFILTERS_ELEMENT_ID),
            ("settings[is_archive_main_query]", "true"),
            ("settings[jsf_signature]", JETSMARTFILTERS_SIGNATURE),
            ("props[page]", str(page)),
            ("paged", str(page)),
            ("indexing_filters[]", JETSMARTFILTERS_INDEXING_FILTERS),
        ]

    @staticmethod
    def _parse_jsf_response(payload: str) -> tuple[int, int, str]:
        found_posts = 0
        max_num_pages = 0
        rendered_html = ""
        objects = []
        with contextlib.suppress(TypeError, ValueError):
            objects.append(json.loads(payload))

        def visit(value: Any) -> None:
            nonlocal found_posts, max_num_pages, rendered_html
            if isinstance(value, str):
                stripped = value.strip()
                if stripped.startswith(("{", "[")):
                    with contextlib.suppress(TypeError, ValueError):
                        visit(json.loads(stripped))
                return
            if isinstance(value, list):
                for item in value:
                    visit(item)
                return
            if not isinstance(value, dict):
                return
            for key, item in value.items():
                normalized = str(key).casefold()
                if normalized == "found_posts":
                    found_posts = max(
                        found_posts, CategoryScraper._to_int(item)
                    )
                elif normalized == "max_num_pages":
                    max_num_pages = max(
                        max_num_pages, CategoryScraper._to_int(item)
                    )
                elif (
                    normalized == "rendered_content"
                    and isinstance(item, str)
                    and len(item) > len(rendered_html)
                ):
                    rendered_html = item
                visit(item)

        for obj in objects:
            visit(obj)
        if found_posts == 0:
            found_posts = CategoryScraper._first_int(
                payload,
                (
                    r'"found_posts"\s*:\s*(\d+)',
                    r"found_posts\s*[:=]\s*(\d+)",
                ),
            )
        if max_num_pages == 0:
            max_num_pages = CategoryScraper._first_int(
                payload,
                (
                    r'"max_num_pages"\s*:\s*(\d+)',
                    r"max_num_pages\s*[:=]\s*(\d+)",
                ),
            )
        if max_num_pages == 0 and found_posts > 0:
            max_num_pages = (
                found_posts + CategoryScraper.PRODUCTS_PER_PAGE - 1
            ) // CategoryScraper.PRODUCTS_PER_PAGE
        return found_posts, max_num_pages, rendered_html

    @staticmethod
    def _parse_jsf_metadata(payload: str) -> tuple[int, int]:
        found_posts, max_num_pages, _ = CategoryScraper._parse_jsf_response(
            payload
        )
        return found_posts, max_num_pages

    @staticmethod
    def _to_int(value: Any) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0

    @staticmethod
    def _first_int(text: str, patterns: tuple[str, ...]) -> int:
        for pattern in patterns:
            match = re.search(pattern, text or "", flags=re.IGNORECASE)
            if match:
                try:
                    return int(match.group(1))
                except (IndexError, TypeError, ValueError):
                    return 0
        return 0

    @staticmethod
    def _category_id(html: str) -> int | None:
        soup = BeautifulSoup(html or "", "html.parser")
        body = soup.body
        if body is not None:
            class_names = body.get("class")
            if isinstance(class_names, (list, tuple)):
                for class_name in class_names:
                    match = re.fullmatch(
                        r"(?:term|product_cat)-(\d+)", str(class_name)
                    )
                    if match:
                        return int(match.group(1))
            for attribute in ("data-term-id", "data-category-id"):
                value = body.get(attribute)
                if isinstance(value, str) and value.isdigit():
                    return int(value)
        patterns = (
            r'data-term-id=["\'](\d+)["\']',
            r'data-category-id=["\'](\d+)["\']',
            r'"filtered_post_id"\s*[:=]\s*["\']?(\d+)',
            r'"_tax_query_product_cat"\s*[:=]\s*["\']?(\d+)',
            r"\bterm-(\d+)\b",
            r"\bproduct_cat-(\d+)\b",
        )
        for pattern in patterns:
            match = re.search(pattern, html or "", flags=re.IGNORECASE)
            if match:
                try:
                    return int(match.group(1))
                except (IndexError, TypeError, ValueError):
                    continue
        return None

    @staticmethod
    def _is_facundo_url(url: str) -> bool:
        return url.startswith("https://stock.importacionesfacundo.com/")

    @staticmethod
    def _jsf_page_url(category_url: str, page: int) -> str:
        return f"{category_url.rstrip('/')}?product-page={page}"

    @staticmethod
    def _fallback_page_url(category_url: str, page: int) -> str:
        return f"{category_url.rstrip('/')}/page/{page}/"

    @staticmethod
    def _declared_total_pages(html: str) -> int:
        patterns = (
            r"\btotalPages\s*[:=]\s*(\d+)",
            r'"max_num_pages"\s*[:=]\s*(\d+)',
            r"\bmax_num_pages\s*[:=]\s*(\d+)",
        )
        return CategoryScraper._first_int(html, patterns)

    @staticmethod
    def _pagination_max_page(html: str) -> int:
        if not html:
            return 0
        numbers = []
        patterns = (
            r"[?&](?:product-page|paged)=(\d+)",
            r"/page/(\d+)(?:/|$)",
            r"data-value=[\"'](\d+)[\"']",
            r"data-page=[\"'](\d+)[\"']",
        )
        for pattern in patterns:
            numbers.extend(
                int(value)
                for value in re.findall(pattern, html, flags=re.IGNORECASE)
            )
        return max(numbers, default=0)

    @staticmethod
    def _page_number(url: str) -> int | None:
        patterns = (
            r"[?&](?:product-page|paged)=(\d+)",
            r"/page/(\d+)(?:/|$)",
        )
        for pattern in patterns:
            match = re.search(pattern, url or "", flags=re.IGNORECASE)
            if match:
                return int(match.group(1))
        return None

    def _fallback_pagination_links(
        self, category_url: str, html: str
    ) -> list[str]:
        soup = self._parse(html)
        links = []
        selector = (
            "a.page-numbers, nav.woocommerce-pagination a, "
            "a[href*='product-page='], a[href*='paged='], "
            "a[href*='page/']"
        )
        for link in soup.select(selector):
            href = link.get("href")
            if isinstance(href, str) and href.strip():
                page_url = urljoin(category_url, href)
                if page_url not in links:
                    links.append(page_url)
        selector = (
            ".jet-filters-pagination__item[data-value], "
            ".jet-filters-pagination__link[data-value]"
        )
        for item in soup.select(selector):
            value = item.get("data-value")
            if not str(value).isdigit() or int(value) <= 1:
                continue
            page_url = self._fallback_page_url(category_url, int(value))
            if page_url not in links:
                links.append(page_url)
        return links

    def _fallback_category_pages(
        self, category_url: str, category_html: str, expected_count: int
    ) -> list[str]:
        pages = [category_url]
        discovered = self._fallback_pagination_links(
            category_url, category_html
        )
        discovered_numbers = {
            number
            for number in (self._page_number(url) for url in discovered)
            if number is not None
        }
        declared_total = self._declared_total_pages(category_html)
        total_pages = max(
            declared_total, self._pagination_max_page(category_html)
        )
        required_pages = 0
        if expected_count > 0:
            required_pages = (
                expected_count + self.PRODUCTS_PER_PAGE - 1
            ) // self.PRODUCTS_PER_PAGE
            if total_pages > 0:
                total_pages = max(total_pages, required_pages)
        for page in range(2, total_pages + 1):
            if page in discovered_numbers:
                continue
            discovered.append(self._fallback_page_url(category_url, page))
            discovered_numbers.add(page)

        pending = list(discovered)
        visited = set(pages)
        while pending:
            page_url = pending.pop(0)
            if page_url in visited:
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
                if next_url not in visited and next_url not in pending:
                    pending.append(next_url)

        if total_pages == 0 and not discovered:
            self._probe_hidden_pages(
                category_url,
                pages,
                visited,
                start_page=2,
                max_page=required_pages or None,
            )
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
        end_page = (
            max_page + 1
            if max_page is not None
            else self.MAX_HIDDEN_PAGE_PROBES + start_page
        )
        for page in range(start_page, end_page):
            page_url = self._fallback_page_url(category_url, page)
            if page_url in visited:
                continue
            html = self.get_html(page_url)
            if not html or not self._product_keys(html):
                break
            visited.add(page_url)
            pages.append(page_url)
            self._cache_category_html(page_url, html)
            for next_url in self._fallback_pagination_links(
                category_url, html
            ):
                if next_url not in visited:
                    page_number = self._page_number(next_url)
                    if page_number and page_number > page:
                        pages.append(next_url)
                        visited.add(next_url)

    def _product_keys(self, html: str, soup=None) -> set[str]:
        soup = soup or self._parse(html)
        keys: set[str] = set()
        if self.product_block_extractor:
            try:
                cards = self.product_block_extractor.extract(soup)
            except (AttributeError, TypeError, ValueError):
                cards = []
            for card in cards or []:
                key = self._product_key_from_card(card)
                if key:
                    keys.add(key)
        if keys:
            return keys
        pattern = re.compile(
            r"\b[A-Z0-9]{1,16}(?:-[A-Z0-9]+)+\b", re.IGNORECASE
        )
        return {match.upper() for match in pattern.findall(html)}

    @staticmethod
    def _product_key_from_card(card) -> str:
        for selector in (
            "p.brxe-a26f34",
            "span.sku",
            ".sku",
            "[sku]",
            "[data-sku]",
            "p[class*='sku']",
            "span[class*='sku']",
        ):
            element = card.select_one(selector)
            if element is None:
                continue
            value = (
                element.get("sku")
                or element.get("data-sku")
                or element.get_text(" ", strip=True)
            )
            match = re.search(
                r"\b[A-Z0-9]{1,16}(?:-[A-Z0-9]+)+\b",
                str(value),
                flags=re.IGNORECASE,
            )
            if match:
                return match.group(0).upper()
        return ""
