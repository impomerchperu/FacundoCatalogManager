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


def test_detail_formatting_markup_participates_in_content_hash():
    service = ProductHashService()
    plain = ScrapedProduct(
        code="FB-1504",
        name="Enmicadora Metálica A4",
        description="Marca: Bright Office",
    )
    formatted = ScrapedProduct(
        code="FB-1504",
        name="Enmicadora Metálica A4",
        description="Marca: Bright Office",
        description_html=(
            '<p style="text-align: center"><strong>Marca:</strong> Bright Office</p>'
        ),
    )

    assert service.generate(plain) != service.generate(formatted)
