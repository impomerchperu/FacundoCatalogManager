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
            <div class="x-tabs_panel-content">
                Material: ABS. Dimensiones: 10 x 5 cm.
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
    assert result["description"] == "Material: ABS. Dimensiones: 10 x 5 cm."


def test_product_extractor_reads_fb4008_technical_summary_outside_tabs():
    html = """
    <html>
        <body>
            <h1>Antiestrés Cerebro Largo</h1>
            <div class="text-content">
                Color: Blanco. Material: Poliuretano. Dimensiones: 75*63*48mm.
                Peso Unitario: 23.5 G. Uso Recomendado: Antiestrés, Promocional.
                Empaque Individual: Bolsa de polietileno. Cantidad Por Caja: 250 Pza.
                Dimensiones Caja: 50*42*42cm. Cubicaje por Caja: 0.0882 m³/CBM
                Peso neto por caja: 5.5 Kg. Peso bruto por caja: 6.25 Kg.
            </div>
            <div id="tab-description" class="woocommerce-Tabs-panel--description">
                Texto comercial que no debe mezclarse con Detalle.
            </div>
            <div id="tab-additional_information">
                Información adicional que no debe mezclarse con Detalle.
            </div>
            <div id="tab-reviews">
                Valoraciones que no deben mezclarse con Detalle.
            </div>
        </body>
    </html>
    """
    result = ProductExtractor().extract(BeautifulSoup(html, "lxml"))

    assert result["description"] == (
        "Material: Poliuretano. Dimensiones: 75*63*48mm. "
        "Peso Unitario: 23.5 G. Uso Recomendado: Antiestrés, Promocional. "
        "Empaque Individual: Bolsa de polietileno. Cantidad Por Caja: 250 Pza. "
        "Dimensiones Caja: 50*42*42cm. Cubicaje por Caja: 0.0882 m³/CBM "
        "Peso neto por caja: 5.5 Kg. Peso bruto por caja: 6.25 Kg."
    )
    assert "Color: Blanco" not in result["description"]
    assert "Texto comercial" not in result["description"]
    assert "Información adicional" not in result["description"]
    assert "Valoraciones" not in result["description"]


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
    soups = (
        "<h2>Modelo 8274A</h2>",
        '<p class="brxe-heading">Modelo F110</p>',
    )

    for html in soups:
        soup = BeautifulSoup(html, "lxml")
        assert ProductExtractor().extract_code(soup) == ""


def test_product_extractor_does_not_guess_color_stock_from_text_order():
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
        "Rojo": 0,
        "Azul": 0,
        "Negro": 0,
    }
    assert result["stock"] == 60


def test_product_extractor_maps_fb6005_stock_by_variant_identity():
    html = """
    <html>
        <h1>Lonchera de Neoprene</h1>
        <p class="brxe-heading">FB-6005</p>
        <div class="text-content">
            Colores disponibles: Azul, Rojo, Negro
        </div>
        <div class="ctn-variation">
            <div class="variaciones-producto tooltip-ui" title="Negro" sku="FB-6005-N">
                <p>4</p>
            </div>
            <div class="variaciones-producto tooltip-ui" title="Rojo" sku="FB-6005-R">
                <p>1022</p>
            </div>
            <div class="variaciones-producto tooltip-ui" title="Azul" sku="FB-6005-A">
                <p>330</p>
            </div>
        </div>
    </html>
    """

    result = ProductExtractor().extract(
        BeautifulSoup(html, "lxml"),
        url="https://example.com/producto/lonchera-de-neoprene/",
        category="Bolsas / Mochilas",
    )

    assert result["color_stock"] == {
        "Azul": 330,
        "Negro": 4,
        "Rojo": 1022,
    }
    assert result["stock"] == 1356


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
        "Rojo": 0,
        "Azul": 0,
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
        "Amarillo": 0,
        "Azul": 0,
    }
    assert result["stock"] == 239


def test_product_extractor_reads_stock_from_each_variant_node_reverse_order():
    html = """
    <html>
        <h1>Lonchera de Neoprene</h1>
        <p class="brxe-heading">FB-6005</p>
        <div class="text-content">
            Colores disponibles: Azul, Rojo, Negro
        </div>
        <div class="ctn-variation">
            <div class="variaciones-producto tooltip-ui" title="Rojo" sku="FB-6005-R">
                <p>1022</p>
            </div>
            <div class="variaciones-producto tooltip-ui" title="Negro" sku="FB-6005-N">
                <p>4</p>
            </div>
            <div class="variaciones-producto tooltip-ui" title="Azul" sku="FB-6005-A">
                <p>330</p>
            </div>
        </div>
    </html>
    """

    result = ProductExtractor().extract(
        BeautifulSoup(html, "lxml"),
        url="https://example.com/producto/lonchera-de-neoprene/",
        category="Bolsas / Mochilas",
    )

    assert result["color_stock"] == {
        "Rojo": 1022,
        "Negro": 4,
        "Azul": 330,
    }
    assert result["stock"] == 1356


def test_product_extractor_does_not_use_description_tabs_or_generic_text_as_detail():
    html = """
    <html>
        <body>
            <div class="text-content">
                Material: Decorativo. Esta es una vista previa comercial.
            </div>
            <div id="tab-description" class="woocommerce-Tabs-panel--description">
                Material: ABS. Texto de la pestaña Descripción que no debe usarse.
            </div>
            <div id="tab-additional_information">
                Material: Acero. Información adicional que no debe usarse.
            </div>
            <div id="tab-reviews">
                Material: Otro. Valoraciones que no deben usarse.
            </div>
        </body>
    </html>
    """
    result = ProductExtractor().extract(BeautifulSoup(html, "lxml"))

    assert result["description"] == ""

def test_product_extractor_rejects_incomplete_authoritative_description_even_if_preview_is_longer():
    html = """
    <html>
        <body>
            <div id="tab-description">
                Material: Poliuretano. Peso neto por caja: 5.5 Kg.
                Peso bruto por...
            </div>
            <div class="text-content">
                This much longer marketing preview ends cleanly but does not
                include the confirmed gross weight, so it must not be used.
            </div>
        </body>
    </html>
    """
    result = ProductExtractor().extract(BeautifulSoup(html, "lxml"))

    assert result["description"] == ""


def test_product_extractor_ignores_color_only_and_generic_other_fields():
    html = """
    <html>
        <body>
            <div id="tab-description">Color: Blanco.</div>
            <div class="text-content">Color: Rojo. Disponible en Azul.</div>
            <div class="x-tabs_panel-content">Información adicional: ABS.</div>
            <div class="color-summary">Colores: Verde, Blanco.</div>
        </body>
    </html>
    """
    result = ProductExtractor().extract(BeautifulSoup(html, "lxml"))

    assert result["description"] == ""


def test_product_extractor_collects_only_technical_detail_panel_blocks():
    html = """
    <html>
        <body>
            <div class="x-tabs_panel-content">
                <div class="brxe-text">
                    Color: Blanco. Material: Poliuretano. Peso neto por caja: 5.5 Kg.
                </div>
                <div class="brxe-text">
                    Peso bruto por caja: 6.25 Kg. Certificado SGS
                </div>
            </div>
            <div id="tab-description" class="woocommerce-Tabs-panel--description">
                Material: Marketing description, not technical Detail.
            </div>
        </body>
    </html>
    """
    result = ProductExtractor().extract(BeautifulSoup(html, "lxml"))

    assert result["description"] == (
        "Material: Poliuretano. Peso neto por caja: 5.5 Kg. "
        "Peso bruto por caja: 6.25 Kg. Certificado SGS"
    )
