from services.scraping.scraped_product_persistence_service import (
    ScrapedProductPersistenceService,
)


def test_save_scraped_products():

    class FakeRepository:
        def __init__(self):

            self.products = []

        def save(self, product):

            self.products.append(product)

    repository = FakeRepository()

    service = ScrapedProductPersistenceService(repository)

    products = [{"code": "P001", "name": "Producto prueba"}]

    result = service.save_products(products)

    assert result == products

    assert repository.products == products
