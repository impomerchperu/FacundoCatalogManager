from bs4 import BeautifulSoup

from scrapers.parser.category_product_parser import (
    CategoryProductParser,
)


def test_extract_product_main_image():

    html = """
    <div class="jsfb-query--querymovil jsfb-filterable">

        <p>FB-1812</p>

        <h2>
            Taza de Plástico
        </h2>


        <img
            src="data:image/svg+xml"
            data-src="https://site.com/Proximo.webp"
        >


        <img
            src="data:image/svg+xml"
            data-src="https://site.com/FB-1812-300x300.webp"
        >


        <img
            src="data:image/svg+xml"
            data-src="https://site.com/Logo-Facundo.webp"
        >


        <img
            src="https://site.com/box-product-03.webp"
        >

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

    assert product.image_url == "https://site.com/FB-1812-300x300.webp"
