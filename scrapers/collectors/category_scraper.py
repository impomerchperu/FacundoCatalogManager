import re
from threading import Lock
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


class CategoryScraper:
    """Scraper de categorías WooCommerce."""

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

        response = requests.get(
            url,
            timeout=20,
            headers={"User-Agent": "Mozilla/5.0"},
        )
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
        """Descubre todas las páginas físicas de una categoría."""
        html = self.get_html(category_url)
        if not html:
            return []

        with self._category_html_cache_lock:
            self._category_html_cache[category_url] = html

        soup = self._parse(html)
        pages = [category_url]
        discovered_page_numbers: set[int] = {1}

        for link in soup.select("a.page-numbers, nav.woocommerce-pagination a"):
            href = link.get("href")
            if not isinstance(href, str) or not href.strip():
                continue
            page_url = urljoin(category_url, href)
            if page_url not in pages:
                pages.append(page_url)
            page_number = self._page_number_from_value(href)
            if page_number:
                discovered_page_numbers.add(page_number)

        # JetSmartFilters puede renderizar paginación sin href. Si existe una
        # URL explícita la respetamos; de lo contrario usamos la ruta
        # canónica /page/N/ para que la página siga siendo procesable.
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
            discovered_page_numbers.add(page_number)

            link = item.select_one("a[href], .jet-filters-pagination__link")
            href = link.get("href") if link else None
            if isinstance(href, str) and href.strip():
                page_url = urljoin(category_url, href)
            else:
                page_url = self._page_url(category_url, page_number)
            if page_url not in pages:
                pages.append(page_url)

        if not expected_count:
            text = soup.get_text(" ", strip=True)
            match = re.search(
                r"(?:Productos?\s+en\s+Stock|Producto\(s\))\s*(\d+)",
                text,
                flags=re.IGNORECASE,
            )
            if match:
                expected_count = int(match.group(1))

        expected_pages = max(
            1,
            (
                max(int(expected_count or 0), 0)
                + self.PRODUCTS_PER_PAGE
                - 1
            )
            // self.PRODUCTS_PER_PAGE,
        )

        # Cuando el HTML no publica todos los enlaces, probamos las formas
        # habituales de WooCommerce/WordPress. La colección deduplica por
        # código para evitar contar dos veces una misma página si el sitio
        # responde con más de una variante válida.
        for page_number in range(2, expected_pages + 1):
            if page_number in discovered_page_numbers:
                continue
            for page_url in self._page_url_variants(category_url, page_number):
                if page_url not in pages:
                    pages.append(page_url)

        return pages

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
        return urljoin(
            category_url.rstrip("/") + "/",
            f"page/{page_number}/",
        )

    @classmethod
    def _page_url_variants(cls, category_url: str, page_number: int) -> list[str]:
        base = category_url.rstrip("/")
        return [
            cls._page_url(category_url, page_number),
            f"{base}/?product-page={page_number}",
            f"{base}/?paged={page_number}",
        ]

    def get_product_blocks(self, url: str):
        html = self.get_html(url)
        if not html:
            return []
        soup = self._parse(html)
        if self.product_block_extractor:
            return self.product_block_extractor.extract(soup)
        return []
