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

    assert result["color_stock"] == {
        "Rojo": 10,
        "Azul": 20,
        "Negro": 30,
    }
    assert result["stock"] == 60


def test_product_extractor_reads_woocommerce_variation_stock_by_color():
    html = """
    <form
        class="variations_form"
        data-product_variations='[
            {"attributes":{"attribute_pa_color":"amarillo"},"max_qty":1520},
            {"attributes":{"attribute_pa_color":"azul"},"max_qty":0},
            {"attributes":{"attribute_pa_color":"blanco"},"max_qty":20}
        ]'
    >
        <select name="attribute_pa_color">
            <option value="amarillo">Amarillo</option>
            <option value="azul">Azul</option>
            <option value="blanco">Blanco</option>
        </select>
    </form>
    """

    soup = BeautifulSoup(html, "lxml")
    result = ProductExtractor().extract(soup)

    assert result["color_stock"] == {
        "Amarillo": 1520,
        "Azul": 0,
        "Blanco": 20,
    }
    assert result["stock"] == 1540
