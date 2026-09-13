from bs4 import BeautifulSoup

from scrapers.extractors.product_link_extractor import ProductLinkExtractor


def test_extract_category_product_urls():
    html = """
    <html>
        <a href="/producto/producto-a/">Producto A</a>
        <a href="/producto/producto-b/">Producto B</a>
        <a href="/otra-ruta">Otra ruta</a>
        <a href="/producto/producto-b/">Duplicado</a>
    </html>
    """

    soup = BeautifulSoup(html, "lxml")
    urls = ProductLinkExtractor().extract(soup)

    assert len(urls) == 2
    assert "/producto/producto-a/" in urls
    assert "/producto/producto-b/" in urls
    assert "/otra-ruta" not in urls
