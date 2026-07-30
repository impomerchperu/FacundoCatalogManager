from services.scraping.scraped_product_service import ScrapedProductService
from services.scraping.scraped_product_mapper import ScrapedProductMapper
from repositories.scraping.scraped_product_repository import ScrapedProductRepository
from database.db_manager import DBManager


class FakeScraper:

    def scrape(self, url):

        html = """
        <html>
            <head>
                <title>Producto Demo</title>
            </head>
            <body>
            </body>
        </html>
        """

        from bs4 import BeautifulSoup

        return BeautifulSoup(
            html,
            "lxml"
        )


def test_scraping_complete_flow():

    db = DBManager(":memory:")

    repository = ScrapedProductRepository(
        db
    )

    scraper = FakeScraper()

    mapper = ScrapedProductMapper()


    service = ScrapedProductService(
        repository,
        scraper,
        mapper
    )


    product = service.scrape_and_save(
        "https://example.com/producto"
    )


    assert product.name == "Producto Demo"


    saved = repository.get_by_url(
        "https://example.com/producto"
    )


    assert saved is not None
    assert saved["name"] == "Producto Demo"