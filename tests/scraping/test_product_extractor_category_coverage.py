from bs4 import BeautifulSoup

from scrapers.extractors.category_product_extractor import (
    CategoryProductExtractor,
)


def test_category_product_extractor_covers_retired_category_parser_fields():
    html = """
    <article>
        <a href="/producto/fb-1812">
            <p class="brxe-a26f34">FB-1812</p>
            <h2 class="brxe-f31760">Taza de Plástico</h2>
            <img data-src="https://site.com/FB-1812.webp">
        </a>
        <div class="content-precio">
            <h3>Precio Muestra</h3>
            <h4>S/ 6.50</h4>
        </div>
        <div class="content-precio">
            <h3>Precio Ciento</h3>
            <h4>S/ 520.00</h4>
        </div>
        <div class="content-precio">
            <h3>Precio Millar</h3>
            <h4>S/ 5000.00</h4>
        </div>
    </article>
    """

    soup = BeautifulSoup(html, "lxml")
    product = CategoryProductExtractor().extract(soup)

    assert product is not None
    assert product.code == "FB-1812"
    assert product.name == "Taza de Plástico"
    assert product.price_sample == 6.50
    assert product.price_hundred == 520
    assert product.price_thousand == 5000
    assert product.image_url == "https://site.com/FB-1812.webp"
