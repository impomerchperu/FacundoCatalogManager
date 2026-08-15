from services.scraping.full_scraping_service import FullScrapingService


def test_full_scraping_runs_image_sync():

    class FakeCategoryService:
        def scrape_all(self):

            return [{"url": "category1"}]

    class FakeProductScraper:
        def scrape_products(self, categories):

            return [{"code": "P001", "image": "image.jpg"}]

    class FakeImageSync:
        def __init__(self):

            self.called = False

        def sync_products(self, products):

            self.called = True

            return products

    image_sync = FakeImageSync()

    service = FullScrapingService(
        category_service=FakeCategoryService(),
        product_scraper=FakeProductScraper(),
        image_sync_adapter=image_sync
    )

    result = service.run()

    assert image_sync.called is True

    assert result["products"] == [{"code": "P001", "image": "image.jpg"}]
