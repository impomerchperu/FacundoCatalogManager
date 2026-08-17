from models.scraping.category import Category
from models.scraping.scraped_product import ScrapedProduct
from models.scraping.sync_result import SyncResult
from services.scraping.catalog_sync_service import CatalogSyncService
from services.scraping.category_product_sync_service import CategoryProductSyncService


class FakeScraper:
    def scrape_category(self, category_url, category_name):
        return [
            ScrapedProduct(
                code="P001",
                name="Producto compartido",
                category=category_name,
                color_stock={
                    "Rojo": 5,
                }
                if category_name == "Jarros"
                else {"Azul": 7},
            ),
        ]


class FakePersistence:
    def save_products(self, products):
        return products


class FakeMapper:
    def map(self, product):
        return product


class FakeImageSync:
    def __init__(self):
        self.received = []

    def sync_products(self, products):
        self.received = list(products)
        return products


class FakeCatalogSync:
    def __init__(self):
        self.received = []

    def consolidate_products(self, products):
        return CatalogSyncService.consolidate_products(products)

    def sync(self, products, expected_products=0):
        self.received = list(products)
        result = SyncResult()
        result.processed = len(self.received)
        result.created = len(self.received)
        result.products_expected = expected_products
        result.products_found = len(self.received)
        result.products_unique = len(self.received)
        result.finish()
        return result


def test_sync_categories_consolidates_before_mapping_and_images():
    image_sync = FakeImageSync()
    catalog_sync = FakeCatalogSync()

    service = CategoryProductSyncService(
        FakeScraper(),
        FakePersistence(),
        mapper=FakeMapper(),
        catalog_sync_service=catalog_sync,
        image_sync_adapter=image_sync,
    )

    categories = [
        Category(name="Jarros", url="/jarros"),
        Category(name="Promocionales", url="/promocionales"),
    ]

    products = service.sync_categories(categories)

    assert len(products) == 1
    assert len(image_sync.received) == 1
    assert len(catalog_sync.received) == 1
    assert products[0].category == "Jarros, Promocionales"
    assert products[0].color_stock == {"Rojo": 5, "Azul": 7}
    assert service.last_sync_result.processed == 1
    assert service.last_sync_result.created == 1
    assert service.last_sync_result.counts_are_consistent
