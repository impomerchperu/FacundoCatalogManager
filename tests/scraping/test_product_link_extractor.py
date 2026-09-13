from bs4 import BeautifulSoup

from scrapers.extractors.product_link_extractor import ProductLinkExtractor


def test_extract_product_links():
    html = """
    <html>
        <body>
            <a href="/producto1">Producto 1</a>
            <a href="/producto2">Producto 2</a>
            <a href="/producto3">Producto 3</a>
            <a href="/producto2">Duplicado</a>
        </body>
    </html>
    """

    soup = BeautifulSoup(html, "lxml")
    urls = ProductLinkExtractor().extract(soup)

    assert len(urls) == 3
    assert "/producto1" in urls
    assert "/producto2" in urls
    assert "/producto3" in urls
