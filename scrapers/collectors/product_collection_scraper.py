from bs4 import BeautifulSoup

from scrapers.extractors.category_product_extractor import CategoryProductExtractor
from scrapers.extractors.product_card_extractor import ProductCardExtractor


class ProductCollectionScraper:
    """
    Recorre una categoría completa.

    Usa tarjetas de categoría generadas
    por Bricks Builder + Jet Engine.

    No depende de WooCommerce.
    """

    def __init__(
        self,
        category_scraper,
        card_extractor=None,
        product_extractor=None,
    ):

        self.category_scraper = category_scraper

        self.card_extractor = card_extractor or ProductCardExtractor()

        self.product_extractor = product_extractor or CategoryProductExtractor()

    def scrape_category(self, category):

        products = []

        pages = self.category_scraper.get_category_pages(category.url)

        for page in pages:
            html = self.category_scraper.get_html(page)

            if not html:
                continue

            soup = BeautifulSoup(html, "html.parser")

            cards = self.card_extractor.extract(soup)

            for card in cards:
                product = self.product_extractor.extract(
                    card, url="", category=category.name
                )

                products.append(product)

        return products
