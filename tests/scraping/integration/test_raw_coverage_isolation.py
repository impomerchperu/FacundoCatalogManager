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


class MutatingCatalogSync:
    @staticmethod
    def consolidate_products(products):
        products[0].category = "Consolidada"
        return [products[0]]

    @staticmethod
    def sync(
        products,
        prune_missing=False,
        expected_products=0,
        expected_category_occurrences=0,
    ):
        del prune_missing
        result = SyncResult(
            products_expected=expected_products,
            expected_category_occurrences=expected_category_occurrences,
            products_found=len(products),
            products_unique=len(products),
        )
        return result


class FakeScraper:
    def __init__(self):
        self.products = {
            "Categoria A": [Product("Categoria A")],
            "Categoria B": [Product("Categoria B")],
        }

    def collect_category(self, category):
        return self.products[category.name]

    def enrich_category_products(self, products, category_name):
        return products


class IdentityMapper:
    def map(self, product):
        return product


def test_raw_category_coverage_is_isolated_from_mutating_consolidation():
    categories = [
        Category("Categoria A", "https://example.com/a/", expected_count=1),
        Category("Categoria B", "https://example.com/b/", expected_count=1),
    ]
    service = CategoryProductSyncService(
        SimpleNamespace(scraper=FakeScraper()),
        persistence_service=SimpleNamespace(),
        mapper=IdentityMapper(),
        catalog_sync_service=MutatingCatalogSync(),
    )

    service.sync_categories(categories)

    result = service.last_sync_result
    assert result.products_found == 2
    assert result.products_unique == 1
    assert result.expected_category_occurrences == 2
    assert result.coverage_gap == 0
    assert result.coverage_complete is True
    assert result.category_summary[0]["products"] == 1
    assert result.category_summary[1]["products"] == 1
