import requests

from models.scraping.category import Category
from services.scraping.category_product_sync_service import CategoryProductSyncService


def test_sync_categories_does_not_hide_persistent_recovery_failure():
    class FakeScraper:
        def __init__(self):
            self.attempts = 0

        def collect_category(self, category):
            self.attempts += 1
            raise requests.exceptions.ReadTimeout(
                f"timed out attempt {self.attempts}"
            )

        def enrich_category_products(self, products, category_name):
            return []

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
        [Category("Categoria fallida", "https://example.com/fail", 1)]
    )

    assert result == []
    assert scraping_service.scraper.attempts == 2
    assert service.last_sync_result.errors == [
        "Error de red en categoría 'Categoria fallida': timed out attempt 1",
        "Reintento fallido en categoría 'Categoria fallida': timed out attempt 2",
    ]
    assert service.last_sync_result.category_summary[0]["products"] == 0
