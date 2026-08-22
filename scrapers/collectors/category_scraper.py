import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


class CategoryScraper:
    """Scraper de categorías WooCommerce."""

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
        response = requests.get(url, timeout=20, headers={"User-Agent": "Mozilla/5.0"})
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
        """Descubre todas las páginas reales e incrustadas de una categoría."""
        html = self.get_html(category_url)
        if not html:
            return []

        pages = [category_url]
        pending_pages = [category_url]
        visited_pages: set[str] = set()
        explicit_page_numbers: set[int] = set()
        implicit_page_numbers: set[int] = set()
        page_product_keys: dict[str, set[str]] = {}
        explicit_pagination_urls: set[str] = set()
        has_explicit_pagination_href = False

        if expected_count <= 0:
            text = self._parse(html).get_text(" ", strip=True)
            match = re.search(
                r"(?:Productos?\s+en\s+Stock|Producto\(s\))\s*(\d+)",
                text,
                flags=re.IGNORECASE,
            )
            if match:
                expected_count = int(match.group(1))

        while pending_pages:
            current_url = pending_pages.pop(0)
            if current_url in visited_pages:
                continue
            visited_pages.add(current_url)
            try:
                current_html = (
                    html
                    if current_url == category_url
                    else self.get_html(current_url)
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

            if (
                current_url == category_url
                and expected_count > 0
                and len(page_product_keys[current_url]) >= expected_count
            ):
                return pages

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
                    explicit_pagination_urls.add(page_url)
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
                    explicit_pagination_urls.add(page_url)
                    if page_url not in pages:
                        pages.append(page_url)
                        newly_discovered.append(page_url)
                else:
                    implicit_page_numbers.add(page_number)

            for page_number in self._page_numbers_from_html(current_html):
                if page_number > 1:
                    explicit_page_numbers.add(page_number)
                    if not has_explicit_pagination_href:
                        implicit_page_numbers.add(page_number)

            if explicit_page_numbers and not has_explicit_pagination_href:
                for page_number in range(2, max(explicit_page_numbers) + 1):
                    implicit_page_numbers.add(page_number)

            for page_url in newly_discovered:
                if page_url not in visited_pages and page_url not in pending_pages:
                    pending_pages.append(page_url)

        if expected_count > self.PRODUCTS_PER_PAGE:
            expected_pages = min(
                self.MAX_PAGE_PROBE,
                max(
                    1,
                    (expected_count + self.PRODUCTS_PER_PAGE - 1)
                    // self.PRODUCTS_PER_PAGE,
                ),
            )
            discovered = self._probe_expected_pages(
                category_url,
                pages,
                page_product_keys.get(category_url, set()),
                expected_pages,
                expected_count,
                explicit_pagination_urls,
            )
            for page_url in discovered:
                if page_url not in pages:
                    pages.append(page_url)
        elif implicit_page_numbers:
            discovered = self._probe_declared_page_numbers(
                category_url,
                pages,
                page_product_keys.get(category_url, set()),
                implicit_page_numbers,
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
            not expected_count
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

    def _discover_embedded_pages(
        self,
        category_url: str,
        pages: list[str],
        discovered: list[str],
        page_product_keys: dict[str, set[str]],
    ) -> None:
        """Continúa la búsqueda cuando una página descubierta contiene más paginación implícita."""
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
        return results

    def _fetch_product_keys(self, url: str) -> tuple[str, set[str]]:
        html = self.get_html(url)
        if not html:
            return "", set()
        soup = self._parse(html)
        return html, self._product_keys(html, soup)

    def _probe_expected_pages(
        self,
        category_url: str,
        known_pages: list[str],
        first_page_keys: set[str],
        expected_pages: int,
        expected_count: int,
        explicit_pagination_urls: set[str] | None = None,
    ) -> list[str]:
        """Encuentra páginas ocultas y se detiene al cubrir el conteo esperado."""
        discovered = []
        seen_keys = set(first_page_keys)
        explicit_pagination_urls = explicit_pagination_urls or set()
        page_numbers_seen = {
            number
            for url in explicit_pagination_urls
            if (number := self._page_number_from_value(url)) and number > 1
        }
        for page_number in range(2, expected_pages + 1):
            if len(seen_keys) >= expected_count:
                break
            if page_number in page_numbers_seen:
                continue
            best_url = None
            best_keys: set[str] = set()
            for candidate, keys in self._probe_page_variants(
                category_url, page_number, known_pages, discovered
            ):
                new_keys = keys - seen_keys
                if len(new_keys) > len(best_keys):
                    best_url = candidate
                    best_keys = new_keys
            if best_url is None or not best_keys:
                continue
            discovered.append(best_url)
            page_numbers_seen.add(page_number)
            seen_keys.update(best_keys)
        return discovered

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
            if best_url is None or not best_keys:
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
        patterns = (
            r"(?:product-page|paged|page)[=/\-](\d+)",
            r"[?&](?:product-page|paged|page)=(\d+)",
            r"(?:data-(?:page|page-number|paged|value))=[\"'](\d+)[\"']",
            r"(?:pageNumber|page_number|currentPage|totalPages)\s*[:=]\s*[\"']?(\d+)",
        )
        for pattern in patterns:
            for match in re.finditer(pattern, html, flags=re.IGNORECASE):
                try:
                    numbers.add(int(match.group(1)))
                except (IndexError, TypeError, ValueError):
                    continue
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
