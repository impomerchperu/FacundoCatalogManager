from services.scraping.catalog_sync_service import CatalogSyncService
from services.scraping.product_diff_service import ProductDiffService
from tests.scraping.catalog_sync_test_doubles import InMemoryCatalogRepository


class Product:
    def __init__(self, code, name, price, category="Categoria A"):
        self.code = code
        self.name = name
        self.price = price
        self.category = category
        self.description = ""
        self.price_sample = 0.0
        self.price_hundred = 0.0
        self.price_thousand = 0.0
        self.stock = 0
        self.colors = []
        self.color_stock = {}
        self.image_url = ""
        self.image_path = ""
        self.image_hash = ""
        self.content_hash = ""
        self.url = ""


def test_catalog_sync_prunes_when_category_occurrences_exceed_unique_products():
    repository = InMemoryCatalogRepository()
    repository.save(Product("OLD001", "Producto obsoleto", 10))
    repository.save(Product("KEEP001", "Producto vigente", 20))

    service = CatalogSyncService(repository, ProductDiffService())
    result = service.sync(
        [Product("KEEP001", "Producto vigente", 20)],
        expected_products=1,
        expected_category_occurrences=2,
    )

    assert result.products_expected == 1
    assert result.expected_category_occurrences == 2
    assert result.products_found == 1
    assert result.products_unique == 1
    assert result.coverage_complete is True
    assert result.deleted == 1
    assert repository.get("OLD001") is None
    assert repository.get("KEEP001") is not None
