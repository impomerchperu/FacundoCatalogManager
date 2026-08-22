import re
from concurrent.futures import ThreadPoolExecutor, as_completed
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
    """Scraper de categorías WooCommerce con paginación Bricks/JetSmartFilters."""

    PRODUCTS_PER_PAGE = 25
    MAX_PAGE_PROBE = 50
    PAGE_VARIANT_WORKERS = 5

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
        self._jsf_metadata_lock = Lock()
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
        self,
        category_url: str,
        expected_count: int = 0,
    ) -> list[str]:
        """Descubre páginas, priorizando metadatos reales de JetSmartFilters."""
        html = self.get_html(category_url)
        if not html:
            return []

        pages = [category_url]
        pending_pages = [category_url]
        visited_pages: set[str] = set()
        explicit_page_numbers: set[int] = set()
        page_product_keys: dict[str, set[str]] = {}
        has_explicit_pagination_href = False
        discovered: list[str] = []

        jsf_count, jsf_pages = self._jet_smart_filters_metadata(
            category_url,
            html,
        )
        if jsf_count > 0:
            expected_count = jsf_count
        if jsf_pages > 0:
            expected_pages = jsf_pages
        elif expected_count > 0:
            expected_pages = max(
                1,
                (expected_count + self.PRODUCTS_PER_PAGE - 1)
                // self.PRODUCTS_PER_PAGE,
            )
        else:
            expected_pages = 0

        while pending_pages:
            current_url = pending_pages.pop(0)
            if current_url in visited_pages:
                continue
            visited_pages.add(current_url)
            try:
                current_html = (
                    html if current_url == category_url else self.get_html(current_url)
                )
            except requests.RequestException:
                if current_url != category_url:
                    continue
                raise
            if not current_html:
                continue

            with self._category_html_cache_lock:
                self._category_html_cache[current_url] = current_html
            soup = self._parse(current_html)
            page_product_keys[current_url] = self._product_keys(current_html, soup)

            newly_discovered: list[str] = []
            for link in soup.select(
                "a.page-numbers, nav.woocommerce-pagination a, "
                "a[href*='product-page='], a[href*='paged='], a[href*='page/']"
            ):
                href = link.get("href")
                if not isinstance(href, str) or not href.strip():
                    continue
                page_url = urljoin(current_url, href)
                page_number = self._page_number_from_value(href)
                if page_number:
                    has_explicit_pagination_href = True
                    explicit_page_numbers.add(page_number)
                if page_url not in pages:
                    pages.append(page_url)
                    newly_discovered.append(page_url)

            for item in soup.select(
                ".jet-filters-pagination__item[data-value], "
                "[data-page], [data-page-number], [data-paged]"
            ):
                raw_value = (
                    item.get("data-value")
                    or item.get("data-page")
                    or item.get("data-page-number")
                    or item.get("data-paged")
                )
                page_number = self._page_number_from_value(raw_value)
                if not page_number or page_number <= 1:
                    continue
                explicit_page_numbers.add(page_number)
                link = item.select_one("a[href], .jet-filters-pagination__link")
                href = link.get("href") if link else None
                if isinstance(href, str) and href.strip():
                    page_url = urljoin(current_url, href)
                    has_explicit_pagination_href = True
                    if page_url not in pages:
                        pages.append(page_url)
                        newly_discovered.append(page_url)

            for page_number in self._page_numbers_from_html(current_html):
                if page_number > 1:
                    explicit_page_numbers.add(page_number)

            for page_url in newly_discovered:
                if page_url not in visited_pages and page_url not in pending_pages:
                    pending_pages.append(page_url)

        if expected_pages > 1 or explicit_page_numbers:
            page_numbers = set(explicit_page_numbers)
            if expected_pages > 1:
                page_numbers.update(range(2, expected_pages + 1))
            discovered = self._probe_declared_page_numbers(
                category_url,
                pages,
                page_product_keys.get(category_url, set()),
                page_numbers,
            )
            for page_url in discovered:
                if page_url not in pages:
                    pages.append(page_url)

        if discovered:
            self._discover_embedded_pages(
                category_url,
                pages,
                discovered,
                page_product_keys,
            )

        if (
            expected_pages == 0
            and not explicit_page_numbers
            and not has_explicit_pagination_href
        ):
            internal_pages = self._probe_internal_pages(
                category_url,
                pages,
                page_product_keys.get(category_url, set()),
            )
            for page_url in internal_pages:
                if page_url not in pages:
                    pages.append(page_url)
        return pages

    def _jet_smart_filters_metadata(
        self,
        category_url: str,
        category_html: str,
    ) -> tuple[int, int]:
        """Obtiene found_posts/max_num_pages de la consulta Bricks real."""
        if not category_url.startswith("https://stock.importacionesfacundo.com/"):
            return 0, 0

        category_id = self._category_id(category_html)
        if category_id is None:
            return 0, 0

        with self._jsf_metadata_lock:
            cached = self._jsf_metadata_cache.get(category_url)
        if cached is not None:
            return cached

        try:
            payload = self._jet_smart_filters_payload(category_id, 1)
            if self.browser and hasattr(self.browser, "post"):
                response_text = self.browser.post(
                    JETSMARTFILTERS_AJAX_URL,
                    data=payload,
                )
            else:
                response = requests.post(
                    JETSMARTFILTERS_AJAX_URL,
                    data=payload,
                    headers=DEFAULT_HEADERS,
                    timeout=20,
                )
                response.raise_for_status()
                response_text = response.text
            found_posts, max_num_pages = self._parse_jsf_metadata(response_text)
        except requests.RequestException:
            return 0, 0

        result = (found_posts, max_num_pages)
        with self._jsf_metadata_lock:
            self._jsf_metadata_cache[category_url] = result
        return result

    @staticmethod
    def _jet_smart_filters_payload(category_id: int, page: int):
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
    def _parse_jsf_metadata(payload: str) -> tuple[int, int]:
        found_patterns = (
            r'"found_posts"\s*:\s*(\d+)',
            r"'found_posts'\s*:\s*(\d+)",
            r"found_posts\s*[:=]\s*(\d+)",
        )
        pages_patterns = (
            r'"max_num_pages"\s*:\s*(\d+)',
            r"'max_num_pages'\s*:\s*(\d+)",
            r"max_num_pages\s*[:=]\s*(\d+)",
        )
        found_posts = CategoryScraper._first_int(payload, found_patterns)
        max_num_pages = CategoryScraper._first_int(payload, pages_patterns)
        if max_num_pages == 0 and found_posts > 0:
            max_num_pages = (
                found_posts + CategoryScraper.PRODUCTS_PER_PAGE - 1
            ) // CategoryScraper.PRODUCTS_PER_PAGE
        return found_posts, max_num_pages

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
        )
        for pattern in patterns:
            match = re.search(pattern, html or "", flags=re.IGNORECASE)
            if match:
                try:
                    return int(match.group(1))
                except (IndexError, TypeError, ValueError):
                    return None
        return None

    def _discover_embedded_pages(
        self,
        category_url: str,
        pages: list[str],
        discovered: list[str],
        page_product_keys: dict[str, set[str]],
    ) -> None:
        """Continúa la búsqueda cuando una página contiene más paginación."""
        frontier = list(discovered)
        processed: set[str] = set()
        while frontier:
            current_url = frontier.pop(0)
            if current_url in processed:
                continue
            processed.add(current_url)
            try:
                with self._category_html_cache_lock:
                    current_html = self._category_html_cache.get(current_url)
                if current_html is None:
                    current_html = self.get_html(current_url)
            except requests.RequestException:
                continue
            if not current_html:
                continue

            soup = self._parse(current_html)
            keys = page_product_keys.setdefault(
                current_url,
                self._product_keys(current_html, soup),
            )
            declared_numbers: set[int] = set()
            explicit_urls: list[str] = []
            for item in soup.select(
                ".jet-filters-pagination__item[data-value], "
                "[data-page], [data-page-number], [data-paged]"
            ):
                raw_value = (
                    item.get("data-value")
                    or item.get("data-page")
                    or item.get("data-page-number")
                    or item.get("data-paged")
                )
                page_number = self._page_number_from_value(raw_value)
                if not page_number or page_number <= 1:
                    continue
                declared_numbers.add(page_number)
                link = item.select_one("a[href], .jet-filters-pagination__link")
                href = link.get("href") if link else None
                if isinstance(href, str) and href.strip():
                    explicit_urls.append(urljoin(current_url, href))
            for page_url in explicit_urls:
                if page_url not in pages:
                    pages.append(page_url)
                    frontier.append(page_url)
            if declared_numbers and not explicit_urls:
                new_pages = self._probe_declared_page_numbers(
                    category_url,
                    pages,
                    keys,
                    declared_numbers,
                )
                for page_url in new_pages:
                    if page_url not in pages:
                        pages.append(page_url)
                        frontier.append(page_url)

    def _probe_page_variants(self, category_url, page_number, known_pages, discovered):
        candidates = [
            candidate
            for candidate in self._page_url_variants(category_url, page_number)
            if candidate not in known_pages and candidate not in discovered
        ]
        if not candidates:
            return []
        results = []
        worker_count = min(self.PAGE_VARIANT_WORKERS, len(candidates))
        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            futures = {
                executor.submit(self._fetch_product_keys, candidate): candidate
                for candidate in candidates
            }
            for future in as_completed(futures):
                candidate = futures[future]
                try:
                    candidate_html, keys = future.result()
                except requests.RequestException:
                    continue
                if not candidate_html:
                    continue
                results.append((candidate, keys))
                if keys:
                    with self._category_html_cache_lock:
                        self._category_html_cache[candidate] = candidate_html
        candidate_order = {
            candidate: index for index, candidate in enumerate(candidates)
        }
        results.sort(key=lambda result: candidate_order[result[0]])
        return results

    def _fetch_product_keys(self, url: str) -> tuple[str, set[str]]:
        html = self.get_html(url)
        if not html:
            return "", set()
        soup = self._parse(html)
        return html, self._product_keys(html, soup)

    def _probe_declared_page_numbers(
        self,
        category_url: str,
        known_pages: list[str],
        first_page_keys: set[str],
        page_numbers: set[int],
    ) -> list[str]:
        """Resuelve páginas declaradas por JSF/Bricks sin href navegable."""
        discovered: list[str] = []
        seen_keys = set(first_page_keys)
        for page_number in sorted(number for number in page_numbers if number > 1):
            best_url = None
            best_keys: set[str] = set()
            for candidate, keys in self._probe_page_variants(
                category_url,
                page_number,
                known_pages,
                discovered,
            ):
                new_keys = keys - seen_keys
                if len(new_keys) > len(best_keys):
                    best_url = candidate
                    best_keys = new_keys
            if best_url is None:
                continue
            discovered.append(best_url)
            seen_keys.update(best_keys)
        return discovered

    def _probe_internal_pages(self, category_url, known_pages, first_page_keys):
        discovered = []
        seen_keys = set(first_page_keys)
        for page_number in range(2, self.MAX_PAGE_PROBE + 1):
            variants = self._probe_page_variants(
                category_url,
                page_number,
                known_pages,
                discovered,
            )
            found_url = None
            found_keys: set[str] = set()
            for candidate, keys in variants:
                new_keys = keys - seen_keys
                if new_keys and len(new_keys) > len(found_keys):
                    found_url = candidate
                    found_keys = new_keys
            if found_url is None:
                break
            discovered.append(found_url)
            seen_keys.update(found_keys)
        return discovered

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
            r"\b[A-Z0-9]{1,16}(?:-[A-Z0-9]+)+\b",
            re.IGNORECASE,
        )
        return {match.upper() for match in pattern.findall(html)}

    @staticmethod
    def _product_key_from_card(card) -> str:
        selectors = (
            "p.brxe-a26f34", "span.sku", ".sku", "[sku]", "[data-sku]",
            "p[class*='sku']", "span[class*='sku']",
        )
        for selector in selectors:
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
        text = card.get_text(" ", strip=True)
        match = re.search(
            r"\b[A-Z0-9]{1,16}(?:-[A-Z0-9]+)+\b",
            text,
            flags=re.IGNORECASE,
        )
        return match.group(0).upper() if match else ""

    @classmethod
    def _page_numbers_from_html(cls, html: str) -> set[int]:
        numbers: set[int] = set()
        exact_patterns = (
            r"(?:product-page|paged|page)[=/\-](\d+)",
            r"[?&](?:product-page|paged|page)=(\d+)",
            r"(?:data-(?:page|page-number|paged|value))=[\"'](\d+)[\"']",
        )
        for pattern in exact_patterns:
            for match in re.finditer(pattern, html, flags=re.IGNORECASE):
                try:
                    numbers.add(int(match.group(1)))
                except (IndexError, TypeError, ValueError):
                    continue

        total_patterns = (
            r"(?:totalPages|max_num_pages)\s*[:=]\s*[\"']?(\d+)",
        )
        for pattern in total_patterns:
            for match in re.finditer(pattern, html, flags=re.IGNORECASE):
                try:
                    total_pages = int(match.group(1))
                except (IndexError, TypeError, ValueError):
                    continue
                if total_pages > 1:
                    numbers.update(range(2, total_pages + 1))
        return numbers

    @classmethod
    def _page_number_from_value(cls, value) -> int | None:
        if value is None:
            return None
        text = str(value).strip()
        if not text:
            return None
        if text.isdigit():
            return int(text)
        for pattern in (
            r"(?:product-page|paged|page)[=/\-](\d+)",
            r"[?&](?:product-page|paged|page)=(\d+)",
            r"(?:^|/)page/(\d+)(?:/|$)",
        ):
            match = re.search(pattern, text, flags=re.IGNORECASE)
            if match:
                try:
                    return int(match.group(1))
                except (IndexError, TypeError, ValueError):
                    return None
        return None

    @classmethod
    def _page_url(cls, category_url: str, page_number: int) -> str:
        return urljoin(category_url.rstrip("/") + "/", f"page/{page_number}/")

    @classmethod
    def _page_url_variants(cls, category_url: str, page_number: int) -> list[str]:
        base = category_url.rstrip("/") + "/"
        return [
            f"{base}?product-page={page_number}",
            cls._page_url(category_url, page_number),
            f"{base}?paged={page_number}",
            f"{base}?page={page_number}",
            f"{category_url.rstrip('/')}?product-page={page_number}",
            f"{category_url.rstrip('/')}?paged={page_number}",
        ]
