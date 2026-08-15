from bs4 import BeautifulSoup

from scrapers.parser.category_product_parser import (
    CategoryProductParser,
)


def test_category_product_parser_extracts_product():

    html = """
    <div class="jsfb-query--querymovil jsfb-filterable">

        <p>FB-1812</p>

        <h2>
            Taza de Plástico
        </h2>

        <img
            data-src="https://site.com/FB-1812.webp"
        >

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

    </div>
    """

    soup = BeautifulSoup(
        html,
        "html.parser",
    )

    block = soup.select_one(".jsfb-query--querymovil")

    parser = CategoryProductParser()

    product = parser.parse(block)

    assert product is not None

    assert product.code == "FB-1812"

    assert product.name == "Taza de Plástico"

    assert product.price_sample == 6.50

    assert product.price_hundred == 520

    assert product.price_thousand == 5000

    assert product.image_url == "https://site.com/FB-1812.webp"
