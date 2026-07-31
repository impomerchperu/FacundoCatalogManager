from services.scraping.full_scraping_service import FullScrapingService


def test_full_scraping_downloads_product_images():

    class FakeCategoryService:

        def scrape_all(self):

            return [
                {
                    "url": "category1"
                }
            ]


    class FakeProductScraper:

        def scrape_products(self, categories):

            return [
                {
                    "code": "P001",
                    "name": "Producto 1",
                    "image": "image1.jpg"
                },
                {
                    "code": "P002",
                    "name": "Producto 2",
                    "image": "image2.jpg"
                }
            ]


    class FakeImageManager:

        def __init__(self):

            self.called = False


        def download_all(
            self,
            products,
            downloader
        ):

            self.called = True

            return [
                "P001.jpg",
                "P002.jpg"
            ]


    class FakeDownloader:
        pass


    service = FullScrapingService(
        category_service=FakeCategoryService(),
        product_scraper=FakeProductScraper(),
        image_manager=FakeImageManager(),
        downloader=FakeDownloader()
    )


    result = service.run()


    assert result["images"] == [
        "P001.jpg",
        "P002.jpg"
    ]