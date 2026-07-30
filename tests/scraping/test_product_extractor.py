from bs4 import BeautifulSoup

from scrapers.product_extractor import ProductExtractor


def test_product_extractor():

    html = """
    <html>
        <head>
            <title>Producto Extractor</title>
        </head>

        <body>

        </body>
    </html>
    """

    soup = BeautifulSoup(
        html,
        "lxml"
    )


    extractor = ProductExtractor()


    result = extractor.extract(
        soup
    )


    assert result["name"] == "Producto Extractor"
    assert result["price"] == 0.0