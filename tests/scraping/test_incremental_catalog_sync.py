from models.scraping.scraped_product import ScrapedProduct
from repositories.scraping.sync_repository import SyncRepository
from services.scraping.catalog_sync_service import CatalogSyncService
from services.scraping.product_diff_service import ProductDiffService


def test_incremental_catalog_sync():

    repository = SyncRepository()

    service = CatalogSyncService(
        repository,
        ProductDiffService(),
    )

    product = ScrapedProduct(
        code="FB-100",
        name="Producto prueba",
        price=10,
        stock=5,
    )

    result = service.sync(
        [product],
    )

    assert result.created == 1
    assert result.updated == 0

    result = service.sync(
        [product],
    )

    assert result.created == 0
    assert result.updated == 0
    assert result.unchanged == 1
