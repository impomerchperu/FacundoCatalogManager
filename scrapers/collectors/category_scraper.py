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
        html = self.get_html(category_url)
        if not html:
            return []

        with self._category_html_cache_lock:
            self._category_html_cache[category_url] = html

        soup = self._parse(html)
        pages = [category_url]

        for link in soup.select("a.page-numbers, nav.woocommerce-pagination a"):
            href = link.get("href")
            if not isinstance(href, str):
                continue
            page_url = urljoin(category_url, href)
            if page_url not in pages:
                pages.append(page_url)

        expected_pages = max(
            1,
            (max(int(expected_count or 0), 0) + self.PRODUCTS_PER_PAGE - 1)
            // self.PRODUCTS_PER_PAGE,
        )
        for page_number in range(2, expected_pages + 1):
            page_url = urljoin(
                category_url.rstrip("/") + "/",
                f"page/{page_number}/",
            )
            if page_url not in pages:
                pages.append(page_url)

        return pages

    def get_product_blocks(self, url: str):
        html = self.get_html(url)
        if not html:
            return []
        soup = self._parse(html)
        if self.product_block_extractor:
            return self.product_block_extractor.extract(soup)
        return []
