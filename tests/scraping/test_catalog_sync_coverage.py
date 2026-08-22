from repositories.scraping.sync_repository import SyncRepository
from services.scraping.catalog_sync_service import CatalogSyncService
from services.scraping.product_diff_service import ProductDiffService


class Product:
    def __init__(self, code, name, category):
        self.code = code
        self.name = name
        self.price = 10
        self.category = category
        self.colors = []
        self.color_stock = {}
        self.url = f"https://example.com/product/{code.lower()}/"


def test_catalog_sync_uses_unique_product_count_for_coverage():
    service = CatalogSyncService(SyncRepository(), ProductDiffService())

    result = service.sync(
        [
            Product("P001", "Producto 1", "Jarros"),
            Product("P001", "Producto 1", "Promocionales"),
            Product("P002", "Producto 2", "Oficina"),
        ],
        expected_products=2,
        expected_category_occurrences=3,
    )

    assert result.products_expected == 2
    assert result.expected_category_occurrences == 3
    assert result.products_found == 3
    assert result.products_unique == 2
    assert result.duplicate_occurrences == 1
    assert result.products_multiple_categories == 1
    assert result.coverage_gap == 0
    assert result.category_occurrence_gap == 0
    assert result.coverage_complete is True


def test_catalog_sync_does_not_enable_prune_without_unique_expected_count():
    service = CatalogSyncService(SyncRepository(), ProductDiffService())

    result = service.sync_full_catalog(
        [Product("P001", "Producto 1", "Jarros")],
        expected_products=None,
        expected_category_occurrences=1,
    )

    assert result.products_expected == 0
    assert result.expected_category_occurrences == 1
    assert result.products_unique == 1
    assert result.coverage_complete is False
    assert result.deleted == 0
