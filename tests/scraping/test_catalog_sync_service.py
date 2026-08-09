from repositories.scraping.sync_repository import SyncRepository
from services.scraping.catalog_sync_service import CatalogSyncService
from services.scraping.product_diff_service import ProductDiffService


class Product:
    def __init__(
        self,
        code,
        name,
        price,
        category="",
        colors=None,
        color_stock=None,
    ):
        self.code = code
        self.name = name
        self.price = price
        self.category = category
        self.colors = list(colors or [])
        self.color_stock = dict(color_stock or {})


def test_catalog_sync_creates_new_product():
    repository = SyncRepository()
    service = CatalogSyncService(repository, ProductDiffService())

    result = service.synchronize([Product("P001", "Producto A", 10)])

    assert result.created == 1


def test_catalog_sync_updates_product():
    repository = SyncRepository()
    repository.save(Product("P001", "Producto A", 10))

    service = CatalogSyncService(repository, ProductDiffService())
    result = service.synchronize([Product("P001", "Producto A", 20)])

    assert result.updated == 1


def test_catalog_sync_consolidates_product_in_multiple_categories():
    repository = SyncRepository()
    service = CatalogSyncService(repository, ProductDiffService())

    products = [
        Product(
            "P002",
            "Producto compartido",
            10,
            category="Jarros Mug",
            colors=["Rojo"],
            color_stock={"Rojo": 5},
        ),
        Product(
            "P002",
            "Producto compartido",
            10,
            category="Promocionales",
            colors=["Azul"],
            color_stock={"Azul": 7},
        ),
    ]

    result = service.synchronize(products)
    stored = repository.get("P002")

    assert result.created == 1
    assert result.processed == 1
    assert stored.category == "Jarros Mug, Promocionales"
    assert stored.colors == ["Rojo", "Azul"]
    assert stored.color_stock == {"Rojo": 5, "Azul": 7}
