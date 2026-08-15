from repositories.scraping.sync_repository import SyncRepository
from services.scraping.catalog_sync_service import CatalogSyncService
from services.scraping.product_diff_service import ProductDiffService


class Product:
    def __init__(
        self,
        code,
        name,
        price,
        stock,
        image_path="img.jpg",
        image_url="url.jpg",
    ):
        self.code = code
        self.name = name
        self.category = "Test"
        self.description = "Producto"
        self.price = price
        self.stock = stock
        self.image_path = image_path
        self.image_url = image_url


def test_incremental_sync_detects_new_product():

    repository = SyncRepository()

    service = CatalogSyncService(repository, ProductDiffService())

    products = [Product("NEW001", "Producto nuevo", 10, 5)]

    result = service.sync(products)

    assert result.created == 1
    assert result.updated == 0
    assert result.unchanged == 0


def test_incremental_sync_detects_updated_product():

    repository = SyncRepository()

    old = Product("UP001", "Producto", 10, 5)

    repository.save(old)

    service = CatalogSyncService(repository, ProductDiffService())

    new = Product("UP001", "Producto", 20, 5)

    result = service.sync([new])

    assert result.updated == 1


def test_incremental_sync_detects_unchanged_product():

    repository = SyncRepository()

    product = Product("SAME001", "Producto", 10, 5)

    repository.save(product)

    service = CatalogSyncService(repository, ProductDiffService())

    result = service.sync([product])

    assert result.unchanged == 1
