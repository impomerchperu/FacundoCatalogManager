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


def test_catalog_sync_keeps_expected_category_assignment_count():
    service = CatalogSyncService(SyncRepository(), ProductDiffService())

    result = service.sync(
        [
            Product("P001", "Producto 1", "Jarros"),
            Product("P001", "Producto 1", "Promocionales"),
            Product("P002", "Producto 2", "Oficina"),
        ],
        expected_products=3,
    )

    assert result.products_expected == 3
    assert result.products_found == 3
    assert result.products_unique == 2
    assert result.duplicate_occurrences == 1
    assert result.products_multiple_categories == 1
    assert result.coverage_gap == 0
