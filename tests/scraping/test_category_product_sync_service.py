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
