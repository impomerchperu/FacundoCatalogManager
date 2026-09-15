from models.scraping.category import Category
from services.scraping.category_product_scraping_service import (
    CategoryProductScrapingService,
)


class FakeScraper:
    def __init__(self):
        self.categories = []

    def scrape_category(self, category):
        self.categories.append(category)
        return [
            type(
                "FakeProduct",
                (),
                {"code": "FB-1812", "name": "Taza de Plástico"},
            )(),
        ]


def test_category_product_scraping_service_forwards_category():
    scraper = FakeScraper()
    service = CategoryProductScrapingService(scraper)

    category = Category(
        name="Jarros Mug",
        url="https://example.com/categoria",
        expected_count=1,
    )

    products = service.scrape_category(
        category.url,
        category,
    )

    assert len(products) == 1
    assert products[0].code == "FB-1812"
    assert products[0].name == "Taza de Plástico"
    assert scraper.categories == [category]


def test_category_product_scraping_service_builds_category_from_legacy_arguments():
    scraper = FakeScraper()
    service = CategoryProductScrapingService(scraper)

    products = service.scrape_category(
        "https://example.com/categoria",
        "Jarros Mug",
        expected_count=3,
    )

    assert len(products) == 1
    assert scraper.categories[0].name == "Jarros Mug"
    assert scraper.categories[0].url == "https://example.com/categoria"
    assert scraper.categories[0].expected_count == 3
