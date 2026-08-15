from bs4 import BeautifulSoup

from scrapers.extractors.product_block_extractor import (
    ProductBlockExtractor,
)


def test_extract_product_blocks():

    html = """
    <div class="jsfb-filterable">
        Producto 1
    </div>

    <div class="jsfb-filterable">
        Producto 2
    </div>
    """

    soup = BeautifulSoup(
        html,
        "html.parser",
    )

    extractor = ProductBlockExtractor()

    products = extractor.extract(soup)

    assert len(products) == 2
