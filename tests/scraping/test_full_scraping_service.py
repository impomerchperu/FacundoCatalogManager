from services.scraping.full_scraping_service import FullScrapingService


def test_full_scraping_service():

    class FakeCategoryScraper:
        def get_product_urls(self, page):
            return ["product1", "product2"]

    class FakePagination:
        def get_pages(self, url):
            return ["page1"]

    class FakeProductScraper:
        def scrape(self, url):
            return {"name": url}

    class FakeProductService:
        def scrape_and_save(self, url):
            return {"saved": url}

    service = FullScrapingService(
        FakeCategoryScraper(),
        FakePagination(),
        FakeProductScraper(),
        FakeProductService(),
    )

    result = service.scrape_category("category")

    assert len(result) == 2
