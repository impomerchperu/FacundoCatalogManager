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
    assert result["image_url"] == (
        "https://stock.importacionesfacundo.com/producto.jpg"
    )
    assert result["description"] == "Descripción demo"


def test_product_extractor_accepts_catalog_code_formats():
    cases = (
        "FB-1703-AZ",
        "PS-1100",
        "KO-001",
        "SKB05X-1",
        "PM810KB-12OZ",
        "F320",
        "F110",
        "R7512",
    )

    for code in cases:
        soup = BeautifulSoup(
            f'<p class="brxe-heading">{code}</p>',
            "lxml",
        )
        assert ProductExtractor().extract_code(soup) == code


def test_product_extractor_does_not_use_unrelated_model_text_as_code():
    soup = BeautifulSoup(
        "<h2>Modelo 8274A</h2>",
        "lxml",
    )

    assert ProductExtractor().extract_code(soup) == ""


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


def test_product_extractor_reads_detail_page_color_links():
    html = """
    <div class="product-information">
        <div>
            Colores
            <a href="/color/negro">Negro</a>
            <a href="/color/azul">Azul</a>
            <a href="/color/rojo">Rojo</a>
        </div>
    </div>
    """

    soup = BeautifulSoup(html, "lxml")
    result = ProductExtractor().extract(soup)

    assert list(result["color_stock"]) == ["Negro", "Azul", "Rojo"]
    assert result["stock"] == 0


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


def test_product_extractor_ignores_script_text_as_color():
    html = """
    <html>
        <body>
            <div class="color-summary">
                Colores: Rojo, Azul
            </div>
            <div>Stock Disponible 10 20</div>
            <div class="color-container">
                <span>Rojo</span>
                <script id="color-scheme-switcher">
                    var acss = {
                        "color_mode":"light",
                        "enable_client_color_preference":"false"
                    };
                    // sourceURL=color-scheme-switcher
                </script>
            </div>
        </body>
    </html>
    """

    soup = BeautifulSoup(html, "lxml")
    result = ProductExtractor().extract(soup)

    assert result["color_stock"] == {
        "Rojo": 10,
        "Azul": 20,
    }
    assert result["stock"] == 30


def test_product_extractor_ignores_javascript_like_color_attributes():
    html = """
    <html>
        <body>
            <div
                class="color-scheme-switcher-frontend-js-extra"
                data-color='var acss = {"color_mode":"light"};'
            >
                <script>
                    var acss = {"color_mode":"light"};
                </script>
            </div>
            <div>Colores: Amarillo, Azul</div>
            <div>Stock Disponible 152 87</div>
        </body>
    </html>
    """

    soup = BeautifulSoup(html, "lxml")
    result = ProductExtractor().extract(soup)

    assert result["color_stock"] == {
        "Amarillo": 152,
        "Azul": 87,
    }
    assert result["stock"] == 239
