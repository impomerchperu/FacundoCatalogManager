import requests

from models.scraping.category import Category
from services.scraping.category_product_sync_service import (
    CategoryProductSyncService,
)


def test_category_product_sync_service():

    class FakeScraper:
        def scrape_category(
            self,
            url,
            category="",
        ):
            return [
                "producto-1",
                "producto-2",
            ]

    class FakePersistence:
        def save_products(
            self,
            products,
        ):
            return products

    service = CategoryProductSyncService(
        FakeScraper(),
        FakePersistence(),
    )

    result = service.sync_category(
        "url",
        "categoria",
    )

    assert len(result) == 2


def test_sync_categories_contains_category_request_exception():
    class Product:
        def __init__(self, code, category):
            self.code = code
            self.category = category

    class FakeScraper:
        def collect_category(self, category):
            if category.name == "Categoria fallida":
                raise requests.exceptions.ReadTimeout("timed out")
            return [("card", "page", Product("OK-001", category.name))]

        def enrich_category_products(self, products, category_name):
            return [item[2] for item in products]

    class FakeScrapingService:
        def __init__(self):
            self.scraper = FakeScraper()

    class FakePersistence:
        def save_products(self, products):
            return products

    service = CategoryProductSyncService(
        FakeScrapingService(),
        FakePersistence(),
    )

    result = service.sync_categories(
        [
            Category("Categoria fallida", "https://example.com/fail", 1),
            Category("Categoria correcta", "https://example.com/ok", 1),
        ]
    )

    assert len(result) == 1
    assert result[0].code == "OK-001"
    assert "Categoria fallida" in service.last_sync_result.errors[0]
    assert service.last_sync_result.category_summary[0]["products"] == 0
    assert service.last_sync_result.category_summary[1]["products"] == 1


def test_sync_categories_recovers_transient_category_request_exception():
    class Product:
        def __init__(self, code, category):
            self.code = code
            self.category = category

    class FakeScraper:
        def __init__(self):
            self.attempts = {}

        def collect_category(self, category):
            attempts = self.attempts.get(category.name, 0) + 1
            self.attempts[category.name] = attempts
            if category.name == "Categoria transitoria" and attempts == 1:
                raise requests.exceptions.ReadTimeout("timed out")
            return [
                (
                    "card",
                    "page",
                    Product("RECOVERED-001", category.name),
                )
            ]

        def enrich_category_products(self, products, category_name):
            return [item[2] for item in products]

    class FakeScrapingService:
        def __init__(self):
            self.scraper = FakeScraper()

    class FakePersistence:
        def save_products(self, products):
            return products

    scraping_service = FakeScrapingService()
    service = CategoryProductSyncService(
        scraping_service,
        FakePersistence(),
    )

    result = service.sync_categories(
        [
            Category("Categoria transitoria", "https://example.com/transitoria", 1),
            Category("Categoria estable", "https://example.com/estable", 1),
        ]
    )

    assert [product.code for product in result] == [
        "RECOVERED-001",
        "RECOVERED-001",
    ]
    assert scraping_service.scraper.attempts["Categoria transitoria"] == 2
    assert scraping_service.scraper.attempts["Categoria estable"] == 1
    assert service.last_sync_result.errors == []
    assert service.last_sync_result.category_summary[0]["products"] == 1
    assert service.last_sync_result.category_summary[1]["products"] == 1
