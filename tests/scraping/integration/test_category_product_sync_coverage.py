from types import SimpleNamespace

from models.scraping.category import Category
from models.scraping.sync_result import SyncResult
from services.scraping.category_product_sync_service import CategoryProductSyncService


class Product:
    def __init__(self, category):
        self.code = "P001"
        self.name = "Producto 1"
        self.category = category
        self.url = "https://example.com/product/p001/"


class FakeScraper:
    def __init__(self, products_by_category):
        self.products_by_category = products_by_category

    def collect_category(self, category):
        return self.products_by_category[category.name]

    def enrich_category_products(self, products, category_name):
        return products


class FakeCatalogSyncService:
    @staticmethod
    def consolidate_products(products):
        return [products[0]]

    @staticmethod
    def sync(
        products, expected_products=0, expected_category_occurrences=0
    ):
        result = SyncResult()
        result.products_expected = expected_products
        result.expected_category_occurrences = expected_category_occurrences
        result.products_found = len(products)
        result.products_unique = len(products)
        return result


class IdentityMapper:
    def map(self, product):
        return product


def test_category_sync_uses_raw_occurrences_for_coverage():
    categories = [
        Category("Categoria A", "https://example.com/a/", expected_count=1),
        Category("Categoria B", "https://example.com/b/", expected_count=1),
    ]
    products_by_category = {
        "Categoria A": [Product("Categoria A")],
        "Categoria B": [Product("Categoria B")],
    }
    service = CategoryProductSyncService(
        SimpleNamespace(scraper=FakeScraper(products_by_category)),
        persistence_service=SimpleNamespace(),
        mapper=IdentityMapper(),
        catalog_sync_service=FakeCatalogSyncService(),
        category_workers=1,
    )

    service.sync_categories(categories, expected_products=1)

    result = service.last_sync_result
    assert result.products_found == 2
    assert result.products_unique == 1
    assert result.products_multiple_categories == 1
    assert result.duplicate_occurrences == 1
    assert result.expected_category_occurrences == 2
    assert result.coverage_gap == 0
    assert result.coverage_complete is True


def test_category_sync_coverage_payload_keeps_occurrences_separate():
    result = SyncResult(
        products_expected=1,
        expected_category_occurrences=2,
        products_found=2,
        products_unique=1,
        products_multiple_categories=1,
    )

    payload = result.to_dict()

    assert payload["reference_category_occurrences"] == 2
    assert payload["actual_category_occurrences"] == 2
    assert payload["unique_products"] == 1
    assert payload["multi_category_products"] == 1
    assert payload["coverage_complete"] is True
