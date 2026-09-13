from models.scraping.scraped_product import ScrapedProduct
from services.scraping.scraped_product_persistence_service import (
    ScrapedProductPersistenceService,
)


class FakeRepository:
    def __init__(self):
        self.products = []

    def save(self, product):
        self.products.append(product)


def test_persistence_service_saves_scraped_products():
    repository = FakeRepository()
    service = ScrapedProductPersistenceService(repository)
    product = ScrapedProduct(
        source="test",
        url="https://example.com/producto",
        code="FB-001",
        name="Producto Demo",
    )

    result = service.save_products([product])

    assert result == [product]
    assert repository.products == [product]
