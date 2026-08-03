from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


class CategoryScraper:
    """
    Scraper de categorías WooCommerce.
    """

    def __init__(self, browser, parser=None, extractor=None):

        self.parser = parser
        self.extractor = extractor

        self.base_url = None

        if isinstance(browser, str):
            self.base_url = browser.rstrip("/")
            self.browser = None
        else:
            self.browser = browser

    # --------------------------------------------------
    # DESCARGA HTML
    # --------------------------------------------------

    def get_html(self, url: str) -> str:

        if self.browser:
            return self.browser.get(url)

        response = requests.get(
            url,
            timeout=20,
            headers={"User-Agent": "Mozilla/5.0"},
        )

        response.raise_for_status()

        return response.text

    # --------------------------------------------------

    def _get_html(self, url: str) -> str:

        return self.get_html(url)

    # --------------------------------------------------
    # PARSER
    # --------------------------------------------------

    def _parse(self, html: str):

        if self.parser and hasattr(self.parser, "parse"):
            return self.parser.parse(html)

        return BeautifulSoup(
            html,
            "html.parser",
        )

    # --------------------------------------------------
    # CATEGORÍAS
    # --------------------------------------------------

    def scrape(self, url: str):

        html = self.get_html(url)

        if not html:
            return []

        if self.parser and hasattr(
            self.parser,
            "extract_categories",
        ):
            return self.parser.extract_categories(html)

        soup = self._parse(html)

        if self.extractor:
            return self.extractor.extract(soup)

        return []

    # --------------------------------------------------
    # PRODUCTOS
    # --------------------------------------------------

    def get_product_urls(self, url: str):

        html = self.get_html(url)

        if not html:
            return []

        soup = self._parse(html)

        if self.extractor:
            return self.extractor.extract(soup)

        return []

    # --------------------------------------------------
    # PAGINACIÓN
    # --------------------------------------------------

    def get_category_pages(
        self,
        category_url: str,
    ) -> list[str]:

        html = self.get_html(category_url)

        if not html:
            return []

        soup = self._parse(html)

        pages: list[str] = [category_url]

        for link in soup.select("a.page-numbers"):
            href = link.get("href")

            # Pyright fix:
            # BeautifulSoup puede devolver varios tipos
            if not isinstance(href, str):
                continue

            page_url = urljoin(
                category_url,
                href,
            )

            if page_url not in pages:
                pages.append(page_url)

        return pages
