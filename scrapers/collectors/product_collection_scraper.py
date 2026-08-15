import re
from typing import Any, Iterable
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from models.scraping.category import Category


class ProductCollectionScraper:
    """Recorre todas las páginas de una categoría y extrae sus productos."""

    def __init__(
        self,
        category_scraper: Any,
        card_extractor: Any,
        product_extractor: Any,
        detail_extractor: Any = None,
    ):
        self.category_scraper = category_scraper
        self.card_extractor = card_extractor
        self.product_extractor = product_extractor
        self.detail_extractor = detail_extractor

    def scrape_category(self, category: Any) -> list[Any]:
        """Extrae todos los productos de una categoría."""
        if isinstance(category, Category):
            category_url = category.url
            category_name = category.name
        else:
            category_url = category
            category_name = ""

        products: list[Any] = []
        pages = self.category_scraper.get_category_pages(category_url)

        for page in pages:
            html = self.category_scraper.get_html(page)
            if not html:
                continue

            soup = BeautifulSoup(html, "html.parser")
            cards = self._extract_cards(soup)

            for card in cards:
                product = self.product_extractor.extract(
                    card,
                    url="",
                    category=category_name,
                )
                product = self._enrich_from_detail_page(
                    card,
                    page,
                    product,
                    category_name,
                )
                products.append(product)

        return products

    def _extract_cards(self, soup: Any) -> list[Any]:
        if callable(self.card_extractor):
            cards = self.card_extractor(soup)
        else:
            cards = self.card_extractor.extract(soup)
        if not isinstance(cards, Iterable):
            raise TypeError("El extractor de tarjetas debe devolver un iterable.")
        return list(cards)

    def _enrich_from_detail_page(
        self,
        card: Any,
        page_url: str,
        product: Any,
        category_name: str,
    ) -> Any:
        """Completa colores y stock desde la página de detalle."""
        if self.detail_extractor is None:
            return product

        link = card.select_one('a[href*="/producto/"]')
        href = link.get("href") if link else ""
        if not isinstance(href, str) or not href:
            return product

        detail_url = urljoin(page_url, href)
        detail_html = self.category_scraper.get_html(detail_url)
        if not detail_html:
            return product

        detail_soup = BeautifulSoup(detail_html, "html.parser")
        detailed_product = self.detail_extractor.extract(
            detail_soup,
            url=detail_url,
            category=category_name,
        )

        detail_color_stock = dict(
            getattr(detailed_product, "color_stock", {})
        )
        card_stock_values = self._stock_values(card)

        if detail_color_stock:
            colors = list(detail_color_stock)
            if len(card_stock_values) == len(colors):
                product.color_stock = dict(
                    zip(colors, card_stock_values, strict=True),
                )
                product.stock = sum(product.color_stock.values())
            elif (
                sum(detail_color_stock.values()) > 0
                or getattr(product, "stock", 0) == 0
            ):
                product.color_stock = detail_color_stock
                product.stock = sum(detail_color_stock.values())
            product.url = detail_url
            return product

        if product.color_stock:
            product.url = detail_url

        return product

    @staticmethod
    def _stock_values(card: Any) -> list[int]:
        """Extrae existencias de la tarjeta, incluyendo el bloque textual visible."""
        values: list[int] = []
        for element in card.select(".variaciones-producto p"):
            text = element.get_text(strip=True)
            if text.isdigit():
                values.append(int(text))
        if values:
            return values

        text = card.get_text(" ", strip=True)
        match = re.search(
            r"stock\s+disponible\s*((?:\d[\d,.]*\s*)+)",
            text,
            flags=re.IGNORECASE,
        )
        if match is None:
            return []

        result: list[int] = []
        for raw_value in re.findall(r"\d[\d,.]*", match.group(1)):
            try:
                result.append(int(float(raw_value.replace(",", ""))))
            except ValueError:
                continue
        return result
