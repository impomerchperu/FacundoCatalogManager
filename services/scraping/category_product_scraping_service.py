from scrapers.collectors.category_scraper import CategoryScraper
from scrapers.parser.category_product_parser import CategoryProductParser


class CategoryProductScrapingService:
    """
    Convierte una página de categoría en una lista de ScrapedProduct.
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
    ):
        products = []

        blocks = self.scraper.get_product_blocks(category_url)

        for block in blocks:
            product = self.parser.parse(
                block,
                category=category,
            )

            if product:
                products.append(product)

        return products
