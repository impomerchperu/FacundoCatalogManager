from models.scraping.scraped_product import ScrapedProduct


def test_create_scraped_product():

    product = ScrapedProduct(
        source="Demo", url="https://demo.com", code="P0010", name="Teclado", price=25.50
    )

    assert product.code == "P0010"
    assert product.name == "Teclado"
    assert product.price == 25.50
