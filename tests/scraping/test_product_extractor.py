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
            <div class="woocommerce-product-details__short-description">
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


def test_product_extractor_reads_fb4008_technical_summary_without_color_line():
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


def test_product_extractor_reads_technical_short_description_without_color_line():
    html = """
    <html>
        <body>
            <h1>Antiestrés Cerebro Largo</h1>
            <div class="woocommerce-product-details__short-description">
                <ul>
                    <li>Color: Blanco.</li>
                    <li>Material: Poliuretano.</li>
                    <li>Dimensiones: 75*63*48mm.</li>
                    <li>Peso Unitario: 23.5 G.</li>
                    <li>Uso Recomendado: Antiestrés, Promocional.</li>
                    <li>Empaque Individual: Bolsa de polietileno.</li>
                    <li>Cantidad Por Caja: 250 Pza.</li>
                    <li>Dimensiones Caja: 50*42*42cm.</li>
                    <li>Cubicaje por Caja: 0.0882 m³/CBM.</li>
                    <li>Peso neto por caja: 5.5 Kg.</li>
                    <li>Peso bruto por caja: 6.25 Kg.</li>
                </ul>
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

    assert result["description"].splitlines() == [
        "Material: Poliuretano.",
        "Dimensiones: 75*63*48mm.",
        "Peso Unitario: 23.5 G.",
        "Uso Recomendado: Antiestrés, Promocional.",
        "Empaque Individual: Bolsa de polietileno.",
        "Cantidad Por Caja: 250 Pza.",
        "Dimensiones Caja: 50*42*42cm.",
        "Cubicaje por Caja: 0.0882 m³/CBM.",
        "Peso neto por caja: 5.5 Kg.",
        "Peso bruto por caja: 6.25 Kg.",
    ]
    assert "Color: Blanco" not in result["description"]
    assert "Texto comercial" not in result["description"]
    assert "Información adicional" not in result["description"]
    assert "Valoraciones" not in result["description"]


def test_product_extractor_preserves_all_authoritative_fields_outside_color_field():
    html = """
    <html><body>
      <p class="brxe-heading">FB-2020</p>
      <div id="brxe-jhzpri">
        <ul>
          <li>Material: Cartón resistente.</li>
          <li>Micrones: 100.</li>
          <li>Piezas: 63.</li>
          <li>Forma: Rectángulo.</li>
          <li>Color: Blanco.</li>
          <li>Caja:</li>
        </ul>
      </div>
      <div id="tab-description">
        Texto de otra pestaña que no debe mezclarse.
      </div>
    </body></html>
    """

    result = ProductExtractor().extract(BeautifulSoup(html, "lxml"))

    assert result["description"].splitlines() == [
        "Material: Cartón resistente.",
        "Micrones: 100.",
        "Piezas: 63.",
        "Forma: Rectángulo.",
        "Caja:",
    ]
    assert "Color: Blanco" not in result["description"]
    assert "otra pestaña" not in result["description"]


def test_authoritative_detail_extraction_can_preserve_source_html_boundaries():
    html = """
    <html><body>
      <p class="brxe-heading">FB-1902</p>
      <div id="brxe-jhzpri">
        <ul>
          <li>Tipo de encuadernado: Espiral simple (tipo coil)</li>
          <li>Hasta 12 hojas (70 g/m²) por pasada</li>
          <li>Capacidad de encuadernado: Hasta 450 hojas</li>
        </ul>
      </div>
    </body></html>
    """
    extractor = ProductExtractor()
    field_found, detail = extractor.extract_authoritative_detail_text(
        BeautifulSoup(html, "lxml"),
        preserve_boundaries=True,
    )

    assert field_found
    assert detail.splitlines() == [
        "Tipo de encuadernado: Espiral simple (tipo coil)",
        "Hasta 12 hojas (70 g/m²) por pasada",
        "Capacidad de encuadernado: Hasta 450 hojas",
    ]


def test_product_extractor_preserves_color_list_inside_description_value():
    html = """
    <html><body>
      <p class="brxe-heading">FB-1308</p>
      <div class="woocommerce-product-details__short-description">
        Descripción: Resaltadores en 5 colores: Fucsia, Naranja, Amarillo,
        Verde y Celeste. Dentro de un pote. Material: Plástico.
        Presentación: Individual en bolsa plástica transparente.
      </div>
    </body></html>
    """

    result = ProductExtractor().extract(BeautifulSoup(html, "lxml"))

    assert (
        "Resaltadores en 5 colores: Fucsia, Naranja, Amarillo, Verde y Celeste."
        in result["description"]
    )
    assert "Dentro de un pote." in result["description"]
    assert "Material: Plástico." in result["description"]
    assert "Presentación: Individual" in result["description"]


def test_product_extractor_reads_technical_detail_from_list_items():
    html = """
    <html>
        <body>
            <h1>Antiestrés Cerebro Largo</h1>
            <div id="brxe-jhzpri" class="brxe-div gap--s bricks-lazy-hidden">
                <ul>
                    <li>Color: Blanco.</li>
                    <li><strong>Material:</strong> Poliuretano.</li>
                    <li><strong>Dimensiones:</strong> 75*63*48mm.</li>
                    <li><strong>Peso Unitario:</strong> 23.5 G.</li>
                    <li><strong>Uso Recomendado:</strong> Antiestrés, Promocional.</li>
                    <li><strong>Empaque Individual:</strong> Bolsa de polietileno.</li>
                    <li><strong>Cantidad Por Caja:</strong> 250 Pza.</li>
                    <li><strong>Dimensiones Caja:</strong> 50*42*42cm.</li>
                    <li><strong>Cubicaje por Caja:</strong> 0.0882 m³/CBM.</li>
                    <li><strong>Peso neto por caja:</strong> 5.5 Kg.</li>
                    <li><strong>Peso bruto por caja:</strong> 6.25 Kg.</li>
                </ul>
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

    assert result["description"].splitlines() == [
        "Material: Poliuretano.",
        "Dimensiones: 75*63*48mm.",
        "Peso Unitario: 23.5 G.",
        "Uso Recomendado: Antiestrés, Promocional.",
        "Empaque Individual: Bolsa de polietileno.",
        "Cantidad Por Caja: 250 Pza.",
        "Dimensiones Caja: 50*42*42cm.",
        "Cubicaje por Caja: 0.0882 m³/CBM.",
        "Peso neto por caja: 5.5 Kg.",
        "Peso bruto por caja: 6.25 Kg.",
    ]
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


def test_product_extractor_keeps_visible_summary_and_ignores_product_tabs():
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

    assert result["description"] == (
        "Material: Decorativo. Esta es una vista previa comercial."
    )

def test_product_extractor_prefers_visible_summary_over_description_tab():
    html = """
    <html>
        <body>
            <div id="tab-description">
                Material: Poliuretano. Peso neto por caja: 5.5 Kg.
                Peso bruto por...
            </div>
            <div class="text-content">
                Descripción: Resumen superior visible. Color: Blanco.
                Presentación: Caja.
            </div>
        </body>
    </html>
    """
    result = ProductExtractor().extract(BeautifulSoup(html, "lxml"))

    assert result["description"] == (
        "Descripción: Resumen superior visible. Presentación: Caja."
    )


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


def test_product_extractor_preserves_explicit_summary_description_prefix():
    html = """
    <html>
        <body>
            <div class="text-content">
                Descripción: producto promocional. Material: texto comercial.
                Dimensiones: datos publicitarios no validados.
            </div>
        </body>
    </html>
    """

    result = ProductExtractor().extract(BeautifulSoup(html, "lxml"))

    assert result["description"] == (
        "Descripción: producto promocional. Material: texto comercial. "
        "Dimensiones: datos publicitarios no validados."
    )



def test_product_extractor_collects_technical_detail_without_color_line():
    html = """
    <html>
        <body>
            <div class="woocommerce-product-details__short-description">
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

    assert result["description"].splitlines() == [
        "Material: Poliuretano. Peso neto por caja: 5.5 Kg.",
        "Peso bruto por caja: 6.25 Kg. Certificado SGS",
    ]


def test_product_extractor_keeps_fb2107_summary_description_and_fields():
    html = """
    <html><body>
      <h1>Set de Vino con Juego de Ajedrez</h1>
      <p style="text-align:left">
        • <strong>Descripción:</strong> Elegante y funcional set que combina
        la pasión por el buen vino y el entretenimiento del ajedrez.<br>
        • <strong>Color:</strong> Blanco.<br>
        • <strong>Contiene:</strong> Sacacorchos, tapón metálico para botella,
        anillo antigoteo y cortagotas/cortacápsulas, más un juego completo
        de piezas de ajedrez.<br>
        • <strong>Presentación:</strong> Caja de cartón Blanca.<br>
        • <strong>Medidas del Estuche:</strong> 15 cm x 17 cm x 4.5 cm.
      </p>
    </body></html>
    """
    result = ProductExtractor().extract(BeautifulSoup(html, "lxml"))
    detail = result["description"]

    assert "Descripción: Elegante y funcional set" in detail
    assert "Color: Blanco" not in detail
    assert "Contiene: Sacacorchos" in detail
    assert "Presentación: Caja de cartón Blanca" in detail
    assert "Medidas del Estuche: 15 cm x 17 cm x 4.5 cm" in detail


def test_product_extractor_ignores_structured_fields_inside_description_tab():
    html = """
    <html><body>
      <div id="tab-description" class="woocommerce-Tabs-panel--description">
        <p>Perfecta para quienes buscan una tinta versátil de gran calidad.</p>
        <ul>
          <li><strong>Calidad Superior:</strong> Formulada para resultados duraderos.</li>
          <li><strong>Compatibilidad Confiable:</strong> Diseñada para impresoras compatibles.</li>
          <li><strong>Procedencia Coreana:</strong> Elaborada en Corea.</li>
          <li><strong>Facilidad de Uso:</strong> Su presentación facilita la recarga.</li>
        </ul>
      </div>
      <div id="tab-additional_information">
        Colores disponibles: Amarillo, Azul, Magenta y Negro.
      </div>
      <div id="tab-reviews">Valoraciones que no deben usarse como Detalle.</div>
    </body></html>
    """
    result = ProductExtractor().extract(BeautifulSoup(html, "lxml"))

    assert result["description"] == ""



def test_product_extractor_recognizes_herra03_technical_fields():
    html = """
    <html><body>
      <ul class="text-content">
        <li>Levantamiento de materiales: Ideal para retirar vinilo de una superficie.</li>
        <li>Proyectos de manualidades: Útil en proyectos creativos.</li>
        <li>Aplicaciones de vinilo: Levanta y posiciona vinilo adhesivo.</li>
        <li>Trabajo en scrapbooking: Ayuda a manipular recortes y adhesivos.</li>
      </ul>
    </body></html>
    """
    result = ProductExtractor().extract(BeautifulSoup(html, "lxml"))
    detail = result["description"]

    assert "Levantamiento de materiales:" in detail
    assert "Proyectos de manualidades:" in detail
    assert "Aplicaciones de vinilo:" in detail
    assert "Trabajo en scrapbooking:" in detail


def test_product_extractor_combines_labeled_details_split_across_paragraphs():
    html = """
    <html><body>
      <div class="brxe-div">
        <p>Levantamiento de materiales: Ideal para retirar vinilo.</p>
        <p>Proyectos de manualidades: Útil en proyectos creativos.</p>
        <p>Aplicaciones de vinilo: Levanta y posiciona vinilo adhesivo.</p>
        <p>Trabajo en scrapbooking: Ayuda a manipular recortes y adhesivos.</p>
      </div>
    </body></html>
    """
    result = ProductExtractor().extract(BeautifulSoup(html, "lxml"))
    detail = result["description"]

    assert "Levantamiento de materiales:" in detail
    assert "Proyectos de manualidades:" in detail
    assert "Aplicaciones de vinilo:" in detail
    assert "Trabajo en scrapbooking:" in detail


def test_product_extractor_ignores_herra03_fields_from_description_tab_paragraphs():
    html = """
    <html><body>
      <div id="tab-description" class="woocommerce-Tabs-panel--description">
        <p>Descripción comercial: herramienta práctica para trabajos creativos.</p>
        <p>Levantamiento de materiales: Ideal para retirar vinilo.</p>
        <p>Proyectos de manualidades: Útil en proyectos creativos.</p>
        <p>Aplicaciones de vinilo: Levanta y posiciona vinilo adhesivo.</p>
        <p>Trabajo en scrapbooking: Ayuda a manipular recortes y adhesivos.</p>
      </div>
    </body></html>
    """
    result = ProductExtractor().extract(BeautifulSoup(html, "lxml"))

    assert result["description"] == ""



def test_product_extractor_recognizes_laminator_and_printer_fields():
    cases = (
        (
            "OL381S",
            """
            <div class="text-content">
              Número de rodillos: 2. Ancho de entrada: 330 mm.
              Espesor máximo de laminación: 0.5 mm. Soporta: 80 a 125 micrones.
              Tiempo de calentamiento: 3 a 5 minutos.
              Velocidad de laminación: 250 mm/min.
              Cortadora con 3 tipos de corte: Recto, Ondulado y Perforado.
            </div>
            """,
            (
                "Número de rodillos: 2",
                "Ancho de entrada: 330 mm",
                "Espesor máximo de laminación: 0.5 mm",
                "Soporta: 80 a 125 micrones",
                "Tiempo de calentamiento: 3 a 5 minutos",
                "Velocidad de laminación: 250 mm/min",
                "Cortadora con 3 tipos de corte: Recto, Ondulado y Perforado",
            ),
        ),
        (
            "MITS-C-CK-D868",
            """
            <div class="text-content">
              Tamaño de impresión (cm): 10 x 15. Rollos por caja: 2.
              Impresiones por rollo: 300.
              Válido para impresoras: CP-D90DW-P, CP-D80DW.
              Opciones de acabado: Brillante y mate.
            </div>
            """,
            (
                "Tamaño de impresión (cm): 10 x 15",
                "Rollos por caja: 2",
                "Impresiones por rollo: 300",
                "Válido para impresoras: CP-D90DW-P, CP-D80DW",
                "Opciones de acabado: Brillante y mate",
            ),
        ),
    )
    extractor = ProductExtractor()
    for code, detail_html, expected_fields in cases:
        soup = BeautifulSoup(
            f"<html><body><p class='brxe-heading'>{code}</p>{detail_html}</body></html>",
            "lxml",
        )
        result = extractor.extract(soup)
        detail = result["description"]
        for expected_field in expected_fields:
            assert expected_field in detail


def test_product_extractor_ignores_semantic_copy_inside_description_tab():
    cases = (
        (
            "PPMPLUS-CIT",
            """
            <div id="tab-description" class="woocommerce-Tabs-panel--description">
              <p>Imprime fotos de alta calidad desde cualquier dispositivo las 24 horas.</p>
              <p>Incluye 1 año de suscripción para 10,000 copias.</p>
              <p>Compatible con impresoras CY-02, CX-02 y CX-02W.</p>
            </div>
            """,
        ),
        (
            "IEV-SFE-CIT",
            """
            <div id="tab-description" class="woocommerce-Tabs-panel--description">
              <p>Incluye NUC dedicado, router WiFi y software especializado.</p>
              <p>Compatible con impresoras Citizen CX-02 / CY-02 / CZ-01.</p>
            </div>
            """,
        ),
        (
            "IKIOSK-ESTANDAR",
            """
            <div id="tab-description" class="woocommerce-Tabs-panel--description">
              <p>Imprime fotos y regalos personalizados con facilidad.</p>
              <p>Compatible con impresoras CX-02, CX-02W y CY-02.</p>
            </div>
            """,
        ),
        (
            "CUCH-02",
            """
            <div id="tab-description" class="woocommerce-Tabs-panel--description">
              <p>Herramienta para cortar materiales más gruesos y resistentes.</p>
            </div>
            """,
        ),
        (
            "CUCH-06",
            """
            <div id="tab-description" class="woocommerce-Tabs-panel--description">
              <p>Esta cuchilla crea perforaciones o piquetes en el material.</p>
            </div>
            """,
        ),
        (
            "CUCH-10",
            """
            <div id="tab-description" class="woocommerce-Tabs-panel--description">
              <p>Útil para cortes profundos en cartón, cuero, fieltro y vinilo.</p>
            </div>
            """,
        ),
    )

    extractor = ProductExtractor()
    for code, html in cases:
        result = extractor.extract(BeautifulSoup(html, "lxml"))
        assert result["description"] == "", code



def test_product_extractor_does_not_promote_generic_marketing_copy_to_detail():
    html = """
    <div id="tab-description" class="woocommerce-Tabs-panel--description">
      <p>El producto ideal para regalar en cualquier ocasión.</p>
      <p>Eleva tu negocio con una experiencia única y resultados increíbles.</p>
    </div>
    """
    result = ProductExtractor().extract(BeautifulSoup(html, "lxml"))

    assert result["description"] == ""


def test_product_extractor_keeps_visible_summary_description_and_ignores_tabs():
    html = """
    <html><body>
      <div class="brxe-div">
        <p style="text-align: left">
          • <strong>Descripción:</strong> Elegante y funcional set que combina
          la pasión por el buen vino y el entretenimiento del ajedrez.<br>
          • <strong>Color:</strong> Blanco.<br>
          • <strong>Contiene:</strong> Sacacorchos, tapón metálico para botella,
          anillo antigoteo y cortagotas más un juego completo de piezas de ajedrez.<br>
          • <strong>Presentación:</strong> Caja de cartón Blanca.<br>
          • <strong>Medidas del Estuche:</strong> 15 cm x 17 cm x 4.5 cm.
        </p>
      </div>
      <div id="tab-description" class="woocommerce-Tabs-panel--description">
        Descripción comercial de la pestaña que no debe añadirse.
        <p>Material: dato de otra pestaña que no debe mezclarse.</p>
      </div>
      <div id="tab-additional_information">
        Información adicional: dato que debe ignorarse.
      </div>
      <div id="tab-reviews">Valoraciones: reseñas que deben ignorarse.</div>
    </body></html>
    """
    result = ProductExtractor().extract(BeautifulSoup(html, "lxml"))
    detail = result["description"]

    assert detail.startswith("Descripción: Elegante y funcional set")
    assert "Contiene: Sacacorchos" in detail
    assert "Presentación: Caja de cartón Blanca." in detail
    assert "Medidas del Estuche: 15 cm x 17 cm x 4.5 cm." in detail
    assert "Color: Blanco" not in detail
    assert "dato de otra pestaña" not in detail
    assert "Información adicional" not in detail
    assert "Valoraciones" not in detail


def test_product_extractor_ignores_role_based_description_tab_content():
    html = """
    <html><body>
      <div role="tabpanel" aria-labelledby="tab-description">
        <div class="text-content">
          Material: ABS. Dimensiones: 10 x 5 cm.
        </div>
      </div>
    </body></html>
    """
    result = ProductExtractor().extract(BeautifulSoup(html, "lxml"))

    assert result["description"] == ""



def test_product_extractor_uses_herra03_visible_summary_not_description_tab():
    html = """
    <html><body>
      <h1>Espátula</h1>
      <p class="sku">HERRA-03</p>
      <div class="woocommerce-product-details__short-description">
        <ul>
          <li>Levantamiento de materiales: Ideal para retirar vinilo y papel adhesivo sin dañar la superficie de corte.</li>
          <li>Proyectos de manualidades: Útil en proyectos que requieren precisión al manipular materiales delicados.</li>
          <li>Aplicaciones de vinilo: Levanta y posiciona vinilo de manera precisa en la superficie de aplicación.</li>
          <li>Trabajo en scrapbooking: Ayuda a manipular pequeños recortes y adhesivos con facilidad.</li>
        </ul>
      </div>
      <div id="tab-description" class="woocommerce-Tabs-panel--description">
        <p>La espátula Silhouette es una herramienta esencial para trabajos creativos.</p>
        <p>Material: Plástico resistente o metal. Longitud: Estándar.</p>
      </div>
      <div id="tab-additional_information">
        <p>Colores: Blanco</p>
      </div>
    </body></html>
    """
    result = ProductExtractor().extract(BeautifulSoup(html, "lxml"))
    detail = result["description"]

    assert result["code"] == "HERRA-03"
    assert "Levantamiento de materiales:" in detail
    assert "Proyectos de manualidades:" in detail
    assert "Aplicaciones de vinilo:" in detail
    assert "Trabajo en scrapbooking:" in detail
    assert "Material: Plástico resistente" not in detail
    assert "Longitud: Estándar" not in detail
    assert "Colores:" not in detail


def test_product_extractor_keeps_visible_thermal_tape_prose_not_tabs():
    html = """
    <html><body>
      <h1>Cinta Térmica 1 x 33 cm</h1>
      <p class="sku">FB-2009</p>
      <div class="woocommerce-product-details__short-description">
        Nuestra cinta térmica es un elemento esencial para tus proyectos de sublimación.
        Esta cinta se adhiere de manera segura a tus diseños en papel de sublimación y
        evita que se muevan durante el proceso de transferencia de calor. Su fuerte
        adherencia y resistencia al calor garantizan que tus creaciones quedarán
        perfectamente fijadas a tus productos.
      </div>
      <div id="tab-description" class="woocommerce-Tabs-panel--description">
        <p>Descripción inferior no válida como origen de Detalle.</p>
      </div>
      <div id="tab-additional_information">
        <p>Colores: Marrón</p>
        <p>TAMAÑOS: 1X33 CM</p>
      </div>
    </body></html>
    """
    result = ProductExtractor().extract(BeautifulSoup(html, "lxml"))
    detail = result["description"]

    assert result["code"] == "FB-2009"
    assert "Nuestra cinta térmica" in detail
    assert "resistencia al calor" in detail
    assert "Descripción inferior" not in detail
    assert "Colores:" not in detail
    assert "TAMAÑOS:" not in detail


def test_product_extractor_reads_authoritative_paragraph_from_brxe_jhzpri():
    html = """
    <html><body>
      <div id="brxe-jhzpri" class="brxe-div gap--s">
        <h3>Set de Vino con Juego de Ajedrez</h3>
        <h3></h3><p></p>
        <p style="text-align: left">
          &#8226; <strong>Descripción:</strong> Elegante y funcional set
          que combina la pasión por el buen vino y el entretenimiento
          del ajedrez.<br>
          &#8226; <strong>Color:</strong> Blanco.<br>
          &#8226; <strong>Contiene:</strong> Sacacorchos, tapón metálico
          para botella, anillo antigoteo y cortagotas, más piezas de ajedrez.<br>
          &#8226; <strong>Presentación:</strong> Caja de cartón Blanca.<br>
          &#8226; <strong>Medidas del Estuche:</strong> 15 cm x 17 cm x 4.5 cm.
        </p>
        <div id="brxe-pvgljs">
          Este producto no está disponible porque no quedan existencias.
        </div>
        <div id="brxe-tscbph">
          <p>SKU: FB-2107</p>
          <p>Categorías: Cocina, Mesa y Hogar</p>
        </div>
        <div id="brxe-miyybm">COMPARTIR:</div>
      </div>
    </body></html>
    """

    detail = ProductExtractor().extract(
        BeautifulSoup(html, "lxml")
    )["description"]

    assert "Descripción: Elegante y funcional set" in detail
    assert "Contiene: Sacacorchos" in detail
    assert "Presentación: Caja de cartón Blanca." in detail
    assert "Medidas del Estuche: 15 cm x 17 cm x 4.5 cm." in detail
    assert "Color:" not in detail
    assert "SKU:" not in detail
    assert "Categorías:" not in detail
    assert "Este producto no está disponible" not in detail
