from services.scraping.category_scraping_service import (
    CategoryScrapingService
)


class FakePaginationService:

    def collect_product_links(
        self,
        category_url
    ):

        return [
            "product_1",
            "product_2",
            "product_3"
        ]


class FakeProductService:

    def __init__(self):

        self.products = []


    def scrape_and_save(
        self,
        url
    ):

        self.products.append(
            url
        )


def test_scrape_category():

    product_service = FakeProductService()

    service = CategoryScrapingService(
        FakePaginationService(),
        product_service
    )


    result = service.scrape_category(
        "category_url"
    )


    assert result == 3

    assert product_service.products == [
        "product_1",
        "product_2",
        "product_3"
    ]