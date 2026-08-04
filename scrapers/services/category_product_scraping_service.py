from scrapers.collectors.category_scraper import CategoryScraper
from scrapers.parser.category_product_parser import (
    CategoryProductParser,
)


class CategoryProductScrapingService:
    """
    Servicio encargado de obtener productos
    desde una categoría WooCommerce.
    """

    def __init__(
        self,
        scraper: CategoryScraper,
        parser: CategoryProductParser,
    ):

        self.scraper = scraper
        self.parser = parser

    def scrape_category(
        self,
        category_url: str,
        category: str = "",
    ) -> list:

        products = []

        pages = self.scraper.get_category_pages(
            category_url,
        )

        for page in pages:
            blocks = self.scraper.get_product_blocks(
                page,
            )

            for block in blocks:
                product = self.parser.parse(
                    block,
                    url=page,
                    category=category,
                )

                if product:
                    products.append(product)

        return products
