from bs4 import BeautifulSoup

from scrapers.extractors.product_extractor import ProductExtractor


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

    soup = BeautifulSoup(html, "lxml")
    extractor = ProductExtractor()
    result = extractor.extract(soup)

    assert result["name"] == "Producto Demo"
    assert result["price"] == 125.50
    assert result["image_url"] == "producto.jpg"
    assert result["description"] == "Descripción demo"


def test_product_extractor_maps_stock_to_visible_colors():
    html = """
    <div class="jsfb-filterable">
        <h2 class="brxe-heading">Producto por colores</h2>
        <p class="brxe-heading">FB-9999</p>
        <div>Colores: Rojo, Azul y Negro.</div>
        <div>Stock Disponible 10 20 30</div>
    </div>
    """

    soup = BeautifulSoup(html, "lxml")
    result = ProductExtractor().extract(soup)

    assert result["colors"] == ["Rojo", "Azul", "Negro"]
    assert result["color_stock"] == {
        "Rojo": 10,
        "Azul": 20,
        "Negro": 30,
    }
    assert result["stock"] == 60
