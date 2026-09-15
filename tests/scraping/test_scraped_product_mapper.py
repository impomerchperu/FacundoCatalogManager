from bs4 import BeautifulSoup

from models.scraping.scraped_product import ScrapedProduct
from scrapers.extractors.product_extractor import ProductExtractor
from services.scraping.product_hash_service import ProductHashService
from services.scraping.scraped_product_mapper import ScrapedProductMapper


def test_product_extractor_populates_all_catalog_prices():
    html = """
    <article>
        <h2 class="brxe-heading">Producto de prueba</h2>
        <p class="brxe-heading">FB-9012</p>
        <div class="content-precio">
            <h3>Precio Muestra</h3>
            <h4>S/ 8.50</h4>
        </div>
        <div class="content-precio">
            <h3>Precio Ciento</h3>
            <h4>S/ 770.00</h4>
        </div>
        <div class="content-precio">
            <h3>Precio Millar</h3>
            <h4>S/ 7500.00</h4>
        </div>
    </article>
    """

    product = ProductExtractor().extract(
        BeautifulSoup(html, "lxml"),
        url="https://example.com/producto/fb-9012/",
        category="Jarros Mug",
    )

    assert product.code == "FB-9012"
    assert product.price_sample == 8.5
    assert product.price_hundred == 770.0
    assert product.price_thousand == 7500.0
    assert product.price == 8.5


def test_scraped_product_mapper_preserves_all_catalog_prices():
    html = """
    <article>
        <h2 class="brxe-heading">Producto de prueba</h2>
        <p class="brxe-heading">FB-9013</p>
        <div class="content-precio">
            <h3>Precio Muestra</h3>
            <h4>S/ 9.25</h4>
        </div>
        <div class="content-precio">
            <h3>Precio Ciento</h3>
            <h4>S/ 820.00</h4>
        </div>
        <div class="content-precio">
            <h3>Precio Millar</h3>
            <h4>S/ 7900.00</h4>
        </div>
    </article>
    """

    scraped = ProductExtractor().extract(
        BeautifulSoup(html, "lxml"),
        url="https://example.com/producto/fb-9013/",
        category="Jarros Mug",
    )
    product = ScrapedProductMapper().to_product(scraped)

    assert product.code == "FB-9013"
    assert product.price == 9.25
    assert product.price_sample == 9.25
    assert product.price_hundred == 820.0
    assert product.price_thousand == 7900.0
    assert product.content_hash


def test_scraped_product_mapper_recomputes_catalog_hash():
    scraped = ScrapedProduct(
        code="FB-9014",
        name="Producto hash",
        price=25,
        price_sample=25,
        stock=7,
        content_hash="legacy-hash-must-not-be-copied",
    )

    product = ScrapedProductMapper().to_product(scraped)
    expected = ProductHashService().generate(scraped)

    assert product.content_hash == expected
    assert product.content_hash != scraped.content_hash
