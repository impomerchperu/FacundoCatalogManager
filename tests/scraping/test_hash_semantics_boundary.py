from models.scraping.scraped_product import ScrapedProduct
from scrapers.factories.scraped_product_factory import ScrapedProductFactory
from scrapers.sync.content_hash import ContentHash
from services.scraping.product_hash_service import ProductHashService


def test_legacy_content_hash_intentionally_ignores_base_price():
    product = ScrapedProduct(
        code="FB-100",
        name="Producto prueba",
        price=10,
        price_sample=10,
        stock=5,
    )
    same_content = ScrapedProduct(
        code="FB-100",
        name="Producto prueba",
        price=20,
        price_sample=10,
        stock=5,
    )

    assert ContentHash.generate(product) == ContentHash.generate(same_content)
    assert ProductHashService().generate(product) != ProductHashService().generate(
        same_content
    )


def test_scraped_product_factory_still_uses_legacy_content_hash_contract():
    product = ScrapedProductFactory.create(
        code="FB-100",
        name="Producto prueba",
        price=10,
        price_sample=10,
        stock=5,
    )

    assert product.content_hash == ContentHash.generate(product)
