from models.scraping.scraped_product import ScrapedProduct
from repositories.scraping.scraped_product_repository import (
    ScrapedProductRepository,
)
from services.scraping.scraped_product_persistence_service import (
    ScrapedProductPersistenceService,
)


def test_persistence_real_product(database):

    repository = ScrapedProductRepository(
        database,
    )

    service = ScrapedProductPersistenceService(
        repository,
    )

    product = ScrapedProduct(
        source="test",
        url="http://producto-test.com",
        code="FB-TEST",
        name="Producto prueba",
    )

    result = service.save_products(
        [product],
    )

    assert len(result) == 1
    assert result[0].code == "FB-TEST"

    saved = repository.get_by_url(
        "http://producto-test.com",
    )

    assert saved is not None
