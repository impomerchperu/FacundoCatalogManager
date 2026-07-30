from database.db_manager import DBManager
from repositories.scraping.scraped_product_repository import ScrapedProductRepository
from models.scraping.scraped_product import ScrapedProduct


def test_create_and_get_scraped_product():

    db = DBManager(":memory:")

    repository = ScrapedProductRepository(
        db
    )

    product = ScrapedProduct(
        source="test",
        url="https://example.com/producto",
        code="SCR001",
        name="Producto Scrapeado",
        category="Test",
        price=25.5,
        image_url="image.jpg",
        description="Producto de prueba"
    )


    repository.create(
        product
    )


    result = repository.get_by_url(
        product.url
    )


    assert result is not None
    assert result["name"] == "Producto Scrapeado"