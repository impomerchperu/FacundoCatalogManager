import contextlib
import json
import re
from threading import Lock
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

    def __init__(
        self,
        browser,
        parser=None,
        category_extractor=None,
        product_block_extractor=None,
    ):
        self.parser = parser
        self.category_extractor = category_extractor
        self.product_block_extractor = product_block_extractor
        self.base_url = None
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
            html = self.browser.get(url)
            if isinstance(html, str):
                return html
            if hasattr(html, "text"):
                return html.text
            return str(html)
        response = requests.get(url, timeout=20, headers=DEFAULT_HEADERS)
        response.raise_for_status()
        return response.text

    def _cache_category_html(self, url: str, html: str) -> None:
        if html:
            with self._category_html_cache_lock:
                self._category_html_cache[url] = html

    def _get_html(self, url: str) -> str:
        return self.get_html(url)

    def _parse(self, html: str):
        if self.parser and hasattr(self.parser, "parse"):
            return self.parser.parse(html)
        return BeautifulSoup(html, "html.parser")

    def scrape(self, url: str):
        html = self.get_html(url)
        if not html:
            return []
        if self.parser and hasattr(self.parser, "extract_categories"):
            return self.parser.extract_categories(html)
        soup = self._parse(html)
        if self.category_extractor:
            return self.category_extractor.extract(soup)
        return []

    def get_product_urls(self, url: str):
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
        """Obtiene todas las páginas reales declaradas por JetSmartFilters."""
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
        expected_count = max(found_posts, expected_count)
        if max_num_pages <= 0:
            if expected_count <= 0:
                return [category_url]
            max_num_pages = (
                expected_count + self.PRODUCTS_PER_PAGE - 1
            ) // self.PRODUCTS_PER_PAGE

        if not first_html:
            raise RuntimeError(
                f"JetSmartFilters no devolvió contenido para {category_url} "
                "en la página 1."
            )

        pages = [category_url]
        self._cache_category_html(category_url, first_html)

        for page_number in range(2, max_num_pages + 1):
            page_url = self._jsf_page_url(category_url, page_number)
            page_found, page_total, rendered_html = self._fetch_jsf_page(
                category_url, category_id, page_number
            )
            if not rendered_html:
                raise RuntimeError(
                    f"JetSmartFilters no devolvió contenido para {category_url} "
                    f"en la página {page_number}/{max_num_pages}."
                )
            if page_total and page_total != max_num_pages:
                raise RuntimeError(
                    f"JetSmartFilters cambió max_num_pages en {category_url}: "
                    f"esperado {max_num_pages}, recibido {page_total}."
                )
            if page_found and found_posts and page_found != found_posts:
                raise RuntimeError(
                    f"JetSmartFilters cambió found_posts en {category_url}: "
                    f"esperado {found_posts}, recibido {page_found}."
                )
            self._cache_category_html(page_url, rendered_html)
            pages.append(page_url)

        if len(pages) != max_num_pages:
            raise RuntimeError(
                f"Paginación incompleta para {category_url}: "
                f"{len(pages)}/{max_num_pages} páginas."
            )
        return pages

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
            return self.browser.post(JETSMARTFILTERS_AJAX_URL, data=payload)
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
            ("defaults[paged]", "1"),
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
        with contextlib.suppress(TypeError, ValueError, json.JSONDecodeError):
            objects.append(json.loads(payload))

        def visit(value):
            nonlocal found_posts, max_num_pages, rendered_html
            if isinstance(value, str):
                stripped = value.strip()
                if stripped.startswith(("{", "[")):
                    with contextlib.suppress(
                        TypeError, ValueError, json.JSONDecodeError
                    ):
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
                    found_posts = max(found_posts, CategoryScraper._to_int(item))
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
        found_posts, max_num_pages, _ = CategoryScraper._parse_jsf_response(payload)
        return found_posts, max_num_pages

    @staticmethod
    def _to_int(value) -> int:
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
        patterns = (
            r"\bterm-(\d+)\b",
            r"\bproduct_cat-(\d+)\b",
            r'data-term-id=["\'](\d+)["\']',
            r'data-category-id=["\'](\d+)["\']',
            r'"filtered_post_id"\s*[:=]\s*["\']?(\d+)',
            r'"_tax_query_product_cat"\s*[:=]\s*["\']?(\d+)',
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
        for link in soup.select(
            "a.page-numbers, nav.woocommerce-pagination a, "
            "a[href*='product-page='], a[href*='paged='], a[href*='page/']"
        ):
            href = link.get("href")
            if isinstance(href, str) and href.strip():
                page_url = urljoin(category_url, href)
                if page_url not in links:
                    links.append(page_url)
        for item in soup.select(
            ".jet-filters-pagination__item[data-value], "
            ".jet-filters-pagination__link[data-value]"
        ):
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
        """Fallback legado para páginas sin metadatos JetSmartFilters."""
        pages = [category_url]
        discovered = self._fallback_pagination_links(category_url, category_html)
        discovered_numbers = {
            number
            for number in (self._page_number(url) for url in discovered)
            if number is not None
        }
        declared_total = self._declared_total_pages(category_html)
        if declared_total > 1:
            total_pages = declared_total
        elif expected_count > 0:
            total_pages = (
                expected_count + self.PRODUCTS_PER_PAGE - 1
            ) // self.PRODUCTS_PER_PAGE
        else:
            total_pages = 0

        if total_pages > 1:
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
            for next_url in self._fallback_pagination_links(category_url, html):
                if next_url not in visited and next_url not in pending:
                    pending.append(next_url)

        if not discovered and total_pages == 0:
            page_number = 2
            while True:
                candidate = self._fallback_page_url(category_url, page_number)
                html = self.get_html(candidate)
                if not html:
                    break
                self._cache_category_html(candidate, html)
                pages.append(candidate)
                page_number += 1

        return pages

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
