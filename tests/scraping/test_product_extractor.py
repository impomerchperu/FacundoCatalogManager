from bs4 import BeautifulSoup

from scrapers.product_extractor import ProductExtractor


def test_product_extractor():

    html = """
    <html>
        <body>

            <h1 class="product-name">
                Producto Demo
            </h1>

            <span class="product-price">
                125.50
            </span>

            <img 
                class="product-image"
                src="producto.jpg"
            >

            <div class="product-description">
                Descripción demo
            </div>

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


    assert result["name"] == "Producto Demo"
    assert result["price"] == 125.50
    assert result["image_url"] == "producto.jpg"
    assert result["description"] == "Descripción demo"