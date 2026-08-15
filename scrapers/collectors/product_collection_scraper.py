from urllib.parse import urljoin

from bs4 import BeautifulSoup

from models.scraping.category import Category


class ProductCollectionScraper:
    """
    Recorre todas las páginas de una categoría y extrae
    los productos encontrados.

    Los productos con múltiples existencias reciben un enriquecimiento
    desde su página de detalle para obtener los colores y asociarlos
    con los valores de stock de la tarjeta de categoría.
    """

    def __init__(
        self,
        category_scraper,
        card_extractor,
        product_extractor,
        detail_extractor=None,
    ):
        self.category_scraper = category_scraper
        self.card_extractor = card_extractor
        self.product_extractor = product_extractor
        self.detail_extractor = detail_extractor

    def scrape_category(self, category):
        """Extrae todos los productos de una categoría."""
        if isinstance(category, Category):
            category_url = category.url
            category_name = category.name
        else:
            category_url = category
            category_name = ""

        products = []
        pages = self.category_scraper.get_category_pages(category_url)

        for page in pages:
            html = self.category_scraper.get_html(page)
            if not html:
                continue

            soup = BeautifulSoup(html, "html.parser")
            cards = self.card_extractor.extract(soup)

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

    def _enrich_from_detail_page(
        self,
        card,
        page_url: str,
        product,
        category_name: str,
    ):
        """Completa colores y stock desde la página de detalle."""
        if self.detail_extractor is None:
            return product

        stock_values = self._stock_values(card)
        if product.color_stock or len(stock_values) <= 1:
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

        colors = list(detailed_product.colors)
        if not colors or len(colors) != len(stock_values):
            return product

        product.colors = colors
        product.color_stock = dict(
            zip(colors, stock_values, strict=True),
        )
        product.stock = sum(product.color_stock.values())
        product.url = detail_url
        return product

    @staticmethod
    def _stock_values(card) -> list[int]:
        values: list[int] = []
        for element in card.select(".variaciones-producto p"):
            text = element.get_text(strip=True)
            if text.isdigit():
                values.append(int(text))
        return values
