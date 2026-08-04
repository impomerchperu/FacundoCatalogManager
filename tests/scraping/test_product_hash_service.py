from models.scraping.scraped_product import ScrapedProduct
from services.scraping.product_hash_service import ProductHashService


def test_same_product_generates_same_hash():

    service = ProductHashService()

    product = ScrapedProduct(
        code="FB-100",
        name="Producto prueba",
        price_sample=10,
        stock=5,
    )

    hash1 = service.generate(product)
    hash2 = service.generate(product)

    assert hash1 == hash2


def test_changed_product_generates_different_hash():

    service = ProductHashService()

    product1 = ScrapedProduct(
        code="FB-100",
        name="Producto prueba",
        stock=5,
    )

    product2 = ScrapedProduct(
        code="FB-100",
        name="Producto prueba",
        stock=10,
    )

    hash1 = service.generate(product1)
    hash2 = service.generate(product2)

    assert hash1 != hash2
