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

    soup = BeautifulSoup(html, "html.parser")
    extractor = ProductBlockExtractor()
    products = extractor.extract(soup)

    assert len(products) == 2


def test_extracts_products_from_catalog_table_beyond_visual_cards():
    html = """
    <div class="jsfb-filterable">
        <span class="sku">FB-0001</span>
        <h3 class="brxe-heading">Producto visible</h3>
        <a href="/producto/visible/"></a>
    </div>
    <table>
        <thead><tr><th>Código</th><th>Imagen</th><th>Producto(s)</th></tr></thead>
        <tbody>
            <tr>
                <td>FB-0001</td><td>Image</td>
                <td><a href="/producto/visible/">Producto visible</a></td>
            </tr>
            <tr>
                <td>FB-0002</td><td>Image</td>
                <td><a href="/producto/oculto/">Producto oculto</a></td>
            </tr>
        </tbody>
    </table>
    """

    soup = BeautifulSoup(html, "html.parser")
    products = ProductBlockExtractor().extract(soup)

    assert len(products) == 2
    extra = products[1]
    assert extra.select_one("span.sku").get_text(strip=True) == "FB-0002"
    assert extra.select_one("h3.brxe-heading").get_text(strip=True) == "Producto oculto"
    assert extra.select_one('a[href="/producto/oculto/"]') is not None
