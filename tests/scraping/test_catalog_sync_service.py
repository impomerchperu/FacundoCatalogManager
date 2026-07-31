from services.scraping.catalog_sync_service import CatalogSyncService
from services.scraping.product_diff_service import ProductDiffService
from services.scraping.sync_repository import SyncRepository


class Product:

    def __init__(
        self,
        code,
        name,
        price
    ):

        self.code = code
        self.name = name
        self.price = price



def test_catalog_sync_creates_new_product():

    repository = SyncRepository()

    service = CatalogSyncService(
        repository,
        ProductDiffService()
    )


    result = service.synchronize(
        [
            Product(
                "P001",
                "Producto A",
                10
            )
        ]
    )


    assert result.created == 1



def test_catalog_sync_updates_product():

    repository = SyncRepository()


    repository.save(
        Product(
            "P001",
            "Producto A",
            10
        )
    )


    service = CatalogSyncService(
        repository,
        ProductDiffService()
    )


    result = service.synchronize(
        [
            Product(
                "P001",
                "Producto A",
                20
            )
        ]
    )


    assert result.updated == 1