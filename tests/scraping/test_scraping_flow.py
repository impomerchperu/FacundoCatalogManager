from database.db_manager import DBManager
from repositories.scraping.scraped_product_repository import ScrapedProductRepository
from services.scraping.scraped_product_mapper import ScrapedProductMapper
from services.scraping.scraped_product_persistence_service import (
    ScrapedProductPersistenceService,
)


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

        return BeautifulSoup(html, "lxml")


def test_scraping_complete_flow():
    db = DBManager(":memory:")
    repository = ScrapedProductRepository(db)
    scraper = FakeScraper()
    mapper = ScrapedProductMapper()
    persistence = ScrapedProductPersistenceService(repository)

    url = "https://example.com/producto"
    scraped_product = mapper.map(scraper.scrape(url), url)
    saved_products = persistence.save_products([scraped_product])

    assert len(saved_products) == 1
    assert saved_products[0].name == "Producto Demo"

    saved = repository.get_by_url(url)

    assert saved is not None
    assert saved["name"] == "Producto Demo"
