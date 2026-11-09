from bs4 import BeautifulSoup

from models.scraping.detail_description_policy import detail_html_matches_text
from scrapers.extractors.category_product_extractor import (
    CategoryProductExtractor,
)


def test_category_product_extractor_does_not_guess_color_stock_from_text_order():
    html = """
    <article>
        <p class="brxe-a26f34">FB-4001-D</p>
        <h2 class="brxe-f31760">Pelota Antiestrés 6.3 cm</h2>
        <div class="text-content">Colores: Dorado, Plateado</div>
        <div class="variaciones-producto">
            <p>6646</p>
            <p>7942</p>
        </div>
    </article>
    """

    card = BeautifulSoup(html, "lxml")
    product = CategoryProductExtractor().extract(card)

    assert product.color_stock == {}
    assert product.stock == 14588


def test_category_product_extractor_maps_visible_stock_to_colors():
    html = """
    <article>
        <p class="brxe-a26f34">FB-5000</p>
        <h2 class="brxe-f31760">Producto por colores</h2>
        <div class="text-content">
            Colores: Amarillo, Azul, Blanco
            Stock Disponible 1520 0 20
        </div>
    </article>
    """

    card = BeautifulSoup(html, "lxml")
    product = CategoryProductExtractor().extract(card)

    assert product.color_stock == {}
    assert product.stock == 1540
    assert product.description == ""


def test_category_product_extractor_falls_back_to_bricks_detail_blocks():
    html = """
    <article>
        <p class="brxe-a26f34">CAM-03</p>
        <h2 class="brxe-f31760">Plotter de Corte Cameo 4 Plus</h2>
        <div class="brxe-text-basic">
            Ancho de Corte: Hasta 15 pulgadas.
            Longitud de Corte: Hasta 10 pies con materiales seleccionados.
            Fuerza de Corte: 5,000 gramos.
            Velocidad de Corte: Hasta 30 cm/segundo.
            Sistema de Motor: Dual.
            Espacio Libre: 3 mm.
        </div>
    </article>
    """

    product = CategoryProductExtractor().extract(BeautifulSoup(html, "lxml"))

    assert "Ancho de Corte: Hasta 15 pulgadas" in product.description
    assert "Longitud de Corte: Hasta 10 pies" in product.description
    assert "Fuerza de Corte: 5,000 gramos" in product.description
    assert "Sistema de Motor: Dual" in product.description
    assert "Espacio Libre: 3 mm" in product.description


def test_category_product_extractor_recognizes_sublimation_fields():
    html = """
    <article>
        <p class="brxe-a26f34">FB-2003</p>
        <h2 class="brxe-f31760">Jarrito de Cerámica</h2>
        <div class="text-content">
            Medida y capacidad: 10.5 cm x 8.5 cm \u2013 444 ml.
            Medida de impresión: 21 x 11 cm.
            Calidad: AAA, alta calidad.
            Material: Cerámica blanca.
        </div>
    </article>
    """

    product = CategoryProductExtractor().extract(BeautifulSoup(html, "lxml"))

    assert "Medida y capacidad: 10.5 cm x 8.5 cm \u2013 444 ml" in product.description
    assert "Medida de impresión: 21 x 11 cm" in product.description
    assert "Calidad: AAA, alta calidad" in product.description
    assert "Material: Cerámica blanca" in product.description


def test_category_product_extractor_omits_empty_final_caja_field():
    html = """
    <article>
        <p class="brxe-a26f34">FB-7080</p>
        <h2 class="brxe-f31760">Laminado A4</h2>
        <div class="text-content">Medida: A4. Paquete: 20 Unidades. Caja:</div>
    </article>
    """

    product = CategoryProductExtractor().extract(BeautifulSoup(html, "lxml"))

    assert product.description == "Medida: A4. Paquete: 20 Unidades."





def test_category_product_extractor_joins_bold_labels_split_across_paragraphs_for_reported_skus():
    codes = (
        "FB-5012",
        "TY-P35AW",
        "FB-3019",
        "FD-2041",
        "FD-2046",
        "SB-2027", "SB-2028", "SB-2029", "SB-2030",
        "SB-2031", "SB-2032", "SB-2033",
        "KF-2034", "KF-2035", "KF-2036", "KF-2037",
        "GP-2020", "GP-2021", "GP-2022", "GP-2023",
        "GP-2024", "GP-2025", "GP-2026",
        "MU-511",
        "HL-9401A", "HL-9403",
        "FB-1504", "SKB05X-1",
    )
    expected = [
        "Medidas: Ancho: 10 cm. Largo: 12 cm.",
        "Material: Plástico.",
        "Descripción: Set de escritorio con accesorios.",
        "Presentación: Individual en caja.",
    ]

    for code in codes:
        html = f"""
        <article>
            <p class="brxe-a26f34">{code}</p>
            <h2 class="brxe-f31760">Producto de prueba {code}</h2>
            <div class="text-content">
                <p><strong>Medidas:</strong></p>
                <p>Ancho: 10 cm. Largo: 12 cm.</p>
                <p><strong>Material:</strong> Plástico.</p>
                <p><b>Descripción:</b></p>
                <p>Set de escritorio con accesorios.</p>
                <p><strong>Presentación:</strong></p>
                <p>Individual en caja.</p>
                <p><strong>Caja:</strong></p>
            </div>
        </article>
        """

        product = CategoryProductExtractor().extract(
            BeautifulSoup(html, "lxml")
        )

        assert product.code == code
        assert product.description.splitlines() == expected


def test_photo_paper_card_omits_empty_box_label_like_other_categories():
    html = """
    <article>
        <p class="brxe-a26f34">FB-7047</p>
        <h2 class="brxe-f31760">Papel Fotográfico Brillante</h2>
        <div class="text-content">
            <ul>
                <li><strong>Gramaje:</strong> 90 g.</li>
                <li><strong>Medida:</strong> A4.</li>
                <li><strong>Paquete:</strong> 20 hojas.</li>
                <li><strong>Caja:</strong></li>
            </ul>
        </div>
    </article>
    """

    product = CategoryProductExtractor().extract(BeautifulSoup(html, "lxml"))

    assert product.description.splitlines() == [
        "Gramaje: 90 g.",
        "Medida: A4.",
        "Paquete: 20 hojas.",
    ]


def test_photo_paper_card_omits_empty_box_and_trailing_share_ui_from_bold_paragraphs():
    html = """
    <article>
        <p class="brxe-a26f34">FB-7030</p>
        <h2 class="brxe-f31760">Papel Fotográfico A4</h2>
        <div class="text-content">
            <p><strong>Medida:</strong> A4</p>
            <p><strong>Paquete:</strong> 20 Unidades</p>
            <p><strong>Caja:</strong></p>
            <p>COMPARTIR:</p>
        </div>
    </article>
    """

    product = CategoryProductExtractor().extract(BeautifulSoup(html, "lxml"))

    assert product.description.splitlines() == [
        "Medida: A4",
        "Paquete: 20 Unidades",
    ]
    assert "Caja:" not in product.description
    assert "COMPARTIR" not in product.description


def test_category_product_extractor_preserves_populated_caja_field():
    html = """
    <article>
        <p class="brxe-a26f34">FB-7080</p>
        <h2 class="brxe-f31760">Laminado A4</h2>
        <div class="text-content">Medida: A4. Paquete: 20 Unidades. Caja: 100 unidades.</div>
    </article>
    """

    product = CategoryProductExtractor().extract(BeautifulSoup(html, "lxml"))

    assert product.description == (
        "Medida: A4. Paquete: 20 Unidades. Caja: 100 unidades."
    )


def test_category_product_extractor_excludes_explicit_price_field_from_detail():
    html = """
    <article>
        <p class="brxe-a26f34">FB-4018</p>
        <h2 class="brxe-f31760">Producto con precio separado</h2>
        <div class="text-content">
            Material: ABS. Precio Ciento: S/ 400.00.
        </div>
        <div class="variaciones-producto"><p>10</p></div>
    </article>
    """

    product = CategoryProductExtractor().extract(BeautifulSoup(html, "lxml"))

    assert product.description == "Material: ABS"
    assert "Precio Ciento" not in product.description


def test_category_product_extractor_does_not_use_commercial_prose_as_detail():
    html = """
    <article>
        <p class="brxe-a26f34">FB-4017</p>
        <h2 class="brxe-f31760">Producto con condiciones comerciales</h2>
        <div class="text-content">
            Precio ciento y precio por caja según volumen;
            consulte las condiciones comerciales.
        </div>
        <div class="variaciones-producto"><p>10</p></div>
    </article>
    """

    product = CategoryProductExtractor().extract(BeautifulSoup(html, "lxml"))

    assert product.description == ""


def test_category_product_extractor_does_not_use_a_color_only_block_as_detail():
    html = """
    <article>
        <p class="brxe-a26f34">FB-4019</p>
        <h2 class="brxe-f31760">Producto con color y sin detalle</h2>
        <div class="text-content">Color: Blanco.</div>
        <div class="variaciones-producto"><p>10</p></div>
    </article>
    """

    product = CategoryProductExtractor().extract(BeautifulSoup(html, "lxml"))

    assert product.description == ""
    assert product.color_stock == {}


def test_category_product_extractor_prefers_detail_text_after_color_only_block():
    html = """
    <article>
        <p class="brxe-a26f34">FB-4015</p>
        <h2 class="brxe-f31760">Producto con detalle</h2>
        <div class="text-content">Color: Blanco.</div>
        <div class="text-content">
            Material: Poliuretano. Peso neto por caja: 5.5 Kg.
        </div>
        <div class="variaciones-producto"><p>10</p></div>
    </article>
    """

    product = CategoryProductExtractor().extract(BeautifulSoup(html, "lxml"))

    assert product.description == (
        "Material: Poliuretano. Peso neto por caja: 5.5 Kg."
    )


def test_category_product_extractor_merges_fb_detail_blocks():
    cases = (
        (
            "FB-1700",
            "Toalla en Tubo",
            (
                "Medidas: Envase Largo: 16 cm, Diámetro: 6.5 cm (Aprox), "
                "Toalla Largo: 80 cm, Ancho: 30 cm",
                "Material: Poliéster y Acrílico Transparente",
                "Presentación: Individual, Bolsa Plástica",
            ),
        ),
        (
            "FB-6005",
            "Lonchera de Neoprene",
            (
                "Medidas: Alto 30 cm, Ancho 29 cm, Interior 14 cm, Espesor 6 mm (Aprox.)",
                "Material: Neoprene",
                "Colores disponibles: Azul, Rojo, Negro",
                "Presentación: Individual, en bolsita plástica transparente",
            ),
        ),
        (
            "FB-6002",
            "Mochilas de Lona",
            (
                "Medidas: 40 x 30 cm",
                "Material: Poliéster 230T",
                "Colores disponibles: Azul, Rojo, Negro, Gris",
                "Presentación: Individual en bolsa de plástico transparente",
            ),
        ),
    )

    for code, name, blocks in cases:
        technical_blocks = "".join(
            f'<div class="text-content">{block}</div>'
            for block in blocks
        )
        html = (
            "<article>"
            f'<p class="brxe-a26f34">{code}</p>'
            f'<h2 class="brxe-f31760">{name}</h2>'
            f"{technical_blocks}"
            "</article>"
        )
        product = CategoryProductExtractor().extract(
            BeautifulSoup(html, "lxml"),
        )

        assert product.code == code
        expected_blocks = [
            block
            for block in blocks
            if not block.casefold().startswith("colores disponibles:")
        ]
        assert product.description == ". ".join(expected_blocks)
        assert "Colores disponibles" not in product.description


def test_category_product_extractor_preserves_boundaries_between_card_list_fields():
    html = """
    <article>
        <p class="brxe-a26f34">IMP-CX02</p>
        <h2 class="brxe-f31760">Impresora Fotográfica Térmica</h2>
        <div class="text-content">
            <ul>
                <li>Impresión térmica (300/600 ppp)</li>
                <li>Velocidad : Desde 8.4s (4\u00d76″) hasta 20.8s (6\u00d79″)</li>
                <li>Modos : Alta velocidad / calidad</li>
                <li>Capacidad : Hasta 400 hojas (4\u00d76″)</li>
                <li>Acabado : Brillante / Mate / Mate fino / Brillo</li>
                <li>Tamaño : 275x366x170mm | 12kg</li>
            </ul>
        </div>
    </article>
    """

    product = CategoryProductExtractor().extract(BeautifulSoup(html, "lxml"))

    assert product.code == "IMP-CX02"
    assert product.description.splitlines() == [
        "Impresión térmica (300/600 ppp)",
        "Velocidad: Desde 8.4s (4\u00d76″) hasta 20.8s (6\u00d79″)",
        "Modos: Alta velocidad / calidad",
        "Capacidad: Hasta 400 hojas (4\u00d76″)",
        "Acabado: Brillante / Mate / Mate fino / Brillo",
        "Tamaño: 275x366x170mm | 12kg",
    ]


def test_category_product_extractor_excludes_description_tab_technical_text():
    html = """
    <article>
        <p class="brxe-a26f34">FB-1701</p>
        <h2 class="brxe-f31760">Almohadilla de Cuello</h2>
        <div id="tab-description" class="woocommerce-Tabs-panel--description">
            <div class="text-content">
                Descripción: producto promocional. Material: texto no validado.
            </div>
        </div>
    </article>
    """

    product = CategoryProductExtractor().extract(BeautifulSoup(html, "lxml"))

    assert product.description == ""


def test_category_product_extractor_preserves_visible_summary_description():
    html = """
    <article>
        <p class="brxe-a26f34">FB-1702</p>
        <h2 class="brxe-f31760">Producto con texto comercial</h2>
        <div class="text-content">
            Descripción: producto promocional. Material: texto comercial,
            no es un atributo técnico verificado. Dimensiones: texto de marketing.
        </div>
    </article>
    """

    product = CategoryProductExtractor().extract(BeautifulSoup(html, "lxml"))

    assert product.description == (
        "Descripción: producto promocional. Material: texto comercial, "
        "no es un atributo técnico verificado. Dimensiones: texto de marketing."
    )


def test_category_product_extractor_keeps_single_total_stock():
    html = """
    <article>
        <p class="brxe-a26f34">FB-4033</p>
        <h2 class="brxe-f31760">Muñeco Minero Antiestrés</h2>
        <div class="variaciones-producto">
            <p>9409</p>
        </div>
    </article>
    """

    card = BeautifulSoup(html, "lxml")
    product = CategoryProductExtractor().extract(card)

    assert product.color_stock == {}
    assert product.stock == 9409


def test_category_product_extractor_recovers_catalog_code_formats():
    for code in ("PS-1100", "F320", "F110", "R7512"):
        html = f"""
        <article>
            <p class="brxe-heading">{code}</p>
            <h2 class="brxe-f31760">Producto de prueba</h2>
        </article>
        """

        card = BeautifulSoup(html, "lxml")

        assert CategoryProductExtractor().extract(card).code == code


def test_category_product_extractor_recovers_code_from_sku_class():
    html = """
    <article>
        <span class="sku">PS-1100</span>
        <h2 class="brxe-f31760">Producto alternativo</h2>
    </article>
    """

    card = BeautifulSoup(html, "lxml")

    assert CategoryProductExtractor().extract(card).code == "PS-1100"


def test_category_product_extractor_rejects_unrelated_model_text():
    html = """
    <article>
        <h2 class="brxe-f31760">Modelo 8274A</h2>
    </article>
    """

    card = BeautifulSoup(html, "lxml")

    assert CategoryProductExtractor().extract(card).code == ""


def test_category_product_extractor_prefers_real_title_over_package_label():
    html = """
    <article>
        <p class="brxe-a26f34">GP-2025</p>
        <h3 class="brxe-heading">(1000) Paq.</h3>
        <h2 class="brxe-f31760">Sobre Manila Pago 11 x 18 cm - 75 grs</h2>
        <div class="content-precio">
            <h3>Precio Muestra</h3>
            <h4>S/ 8.00</h4>
        </div>
        <div class="content-precio">
            <h3>Precio Ciento</h3>
            <h4>S/ 16.00</h4>
        </div>
        <div class="content-precio">
            <h3>Precio Millar</h3>
            <h4>S/ 152.00</h4>
        </div>
    </article>
    """

    card = BeautifulSoup(html, "lxml")
    product = CategoryProductExtractor().extract(card)

    assert product.code == "GP-2025"
    assert product.name == "Sobre Manila Pago 11 x 18 cm - 75 grs"
    assert product.price == 8.0
    assert product.price_sample == 8.0
    assert product.price_hundred == 16.0
    assert product.price_thousand == 152.0


def test_category_product_extractor_reads_stock_from_each_variant_node():
    html = """
    <article>
        <p class="brxe-a26f34">FB-6005</p>
        <h2 class="brxe-f31760">Lonchera de Neoprene</h2>
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
    </article>
    """

    card = BeautifulSoup(html, "lxml")
    product = CategoryProductExtractor().extract(card)

    assert product.color_stock == {
        "Negro": 4,
        "Rojo": 1022,
        "Azul": 330,
    }
    assert product.stock == 1356



def test_category_product_extractor_does_not_split_unbold_value_colons():
    html = """
    <article>
        <p class="brxe-a26f34">HL-9401A</p>
        <h2 class="brxe-f31760">Set de escritorio</h2>
        <div class="text-content">
            <p><strong>Medidas</strong>: Ancho: 8 cm. Largo: 9 cm. Total: 17 cm.</p>
            <p><strong>Descripción:</strong> Estuche que contiene: 1 engrapadora,
            1 tijera y 1 dispensador. Total: 3 accesorios. Color: negro.</p>
            <p><strong>Presentación:</strong> Individual en estuche plástico.</p>
        </div>
    </article>
    """
    product = CategoryProductExtractor().extract(BeautifulSoup(html, "lxml"))

    assert product.description.splitlines() == [
        "Medidas: Ancho: 8 cm. Largo: 9 cm. Total: 17 cm.",
        "Descripción: Estuche que contiene: 1 engrapadora, 1 tijera y 1 dispensador. Total: 3 accesorios.",
        "Presentación: Individual en estuche plástico.",
    ]


def test_category_product_extractor_keeps_summary_description_and_removes_color():
    html = """
    <article>
        <p class="brxe-a26f34">FB-2107</p>
        <h2 class="brxe-f31760">Set de Vino con Juego de Ajedrez</h2>
        <div class="text-content">
            <p>
                • <strong>Descripción:</strong> Elegante y funcional set que
                combina la pasión por el buen vino y el entretenimiento del ajedrez.<br>
                • <strong>Color:</strong> Blanco.<br>
                • <strong>Contiene:</strong> Sacacorchos, tapón metálico para botella
                y un juego completo de piezas de ajedrez.<br>
                • <strong>Presentación:</strong> Caja de cartón Blanca.<br>
                • <strong>Medidas del Estuche:</strong> 15 cm x 17 cm x 4.5 cm.
            </p>
        </div>
    </article>
    """
    product = CategoryProductExtractor().extract(BeautifulSoup(html, "lxml"))

    assert product.description.startswith("Descripción: Elegante y funcional set")
    assert "Color:" not in product.description
    assert "Contiene: Sacacorchos" in product.description
    assert "Presentación: Caja de cartón Blanca" in product.description
    assert "Medidas del Estuche: 15 cm x 17 cm x 4.5 cm" in product.description


def test_category_product_extractor_keeps_populated_fields_before_empty_shipping_labels():
    html = """
    <article>
        <p class="brxe-a26f34">FB-5016</p>
        <h2 class="brxe-f31760">Wincha Multiherramienta Eliza 3m</h2>
        <div class="text-content">
            <p>Color: Negro.</p>
            <p>Material: Bambú y ABS.</p>
            <p>Dimensiones: 9.8*6*2.5cm.</p>
            <p>Peso Unitario: 105.5 G.</p>
            <p>Uso Recomendado: Medir distancias y longitudes + Marcar y anotar notas.</p>
            <p>Empaque Individual: Individual, caja diseño kraft.</p>
            <p>Cantidad Por Caja: 100 Pza.</p>
            <p>Dimensiones Caja:</p>
            <p>Cubicaje por Caja: m³/CBM</p>
            <p>Peso neto por caja:</p>
            <p>Peso bruto por caja:</p>
        </div>
    </article>
    """
    product = CategoryProductExtractor().extract(BeautifulSoup(html, "lxml"))

    assert product.code == "FB-5016"
    assert "Color:" not in product.description
    for field in (
        "Material: Bambú y ABS",
        "Dimensiones: 9.8*6*2.5cm",
        "Peso Unitario: 105.5 G",
        "Uso Recomendado: Medir distancias y longitudes",
        "Empaque Individual: Individual, caja diseño kraft",
        "Cantidad Por Caja: 100 Pza",
        "Cubicaje por Caja: m³/CBM",
    ):
        assert field in product.description

    for empty_field in (
        "Dimensiones Caja:",
        "Peso neto por caja:",
        "Peso bruto por caja:",
    ):
        assert empty_field not in product.description


def test_category_product_extractor_separates_adjacent_bold_empty_fields():
    html = """
    <article>
        <p class="brxe-a26f34">FB-2029</p>
        <h2 class="brxe-f31760">Azulejo sublimable</h2>
        <div class="text-content">
            <p><strong>Material:</strong> Arcilla.</p>
            <p><strong>Dimensiones:</strong> 30*20cm.</p>
            <p><strong>Uso Recomendado:</strong> Azulejo sublimable.</p>
            <p><strong>Empaque Individual:</strong> <strong>Cantidad Por Caja:</strong> 24 Pza.</p>
            <p><strong>Dimensiones Caja:</strong> 31*19*21cm.</p>
            <p><strong>Cubicaje por Caja:</strong> 0.012369 m³/CBM.</p>
        </div>
    </article>
    """
    product = CategoryProductExtractor().extract(BeautifulSoup(html, "lxml"))

    assert product.code == "FB-2029"
    assert product.description.splitlines() == [
        "Material: Arcilla.",
        "Dimensiones: 30*20cm.",
        "Uso Recomendado: Azulejo sublimable.",
        "Cantidad Por Caja: 24 Pza.",
        "Dimensiones Caja: 31*19*21cm.",
        "Cubicaje por Caja: 0.012369 m³/CBM.",
    ]
    assert "Empaque Individual: Cantidad Por Caja:" not in product.description

def test_category_product_extractor_ignores_text_nested_in_description_tab():
    html = """
    <article>
        <p class="brxe-a26f34">FB-9991</p>
        <h2 class="brxe-f31760">Producto con datos solo en pestaña</h2>
        <div class="x-tabs_panel-content">
            <div class="text-content">
                Material: ABS. Dimensiones: 10 x 5 cm.
            </div>
        </div>
    </article>
    """
    product = CategoryProductExtractor().extract(BeautifulSoup(html, "lxml"))

    assert product.description == ""


def test_category_product_extractor_ignores_role_based_description_tab_content():
    html = """
    <article>
        <p class="brxe-a26f34">FB-9992</p>
        <h2 class="brxe-f31760">Producto con panel de pestaña</h2>
        <div role="tabpanel" aria-labelledby="tab-description">
            <div class="text-content">
                Material: ABS. Dimensiones: 10 x 5 cm.
            </div>
        </div>
    </article>
    """
    product = CategoryProductExtractor().extract(BeautifulSoup(html, "lxml"))

    assert product.description == ""


def test_empty_text_content_shell_uses_multiple_visible_fallback_detail_fields():
    html = """
    <article>
        <p class="brxe-a26f34">FB-5016</p>
        <h2 class="brxe-f31760">Wincha Multiherramienta Eliza 3m</h2>
        <div class="text-content"></div>
        <div class="brxe-text-basic">
            <p>Medidas: 6 cm x 9.6 cm x 2.2 cm (Aprox)</p>
            <p>Material: Bambú y ABS</p>
            <p>Funciones: 7 funciones (cinta métrica de 3 m, destornillador con puntas planas, philips y allen, nivel integrado)</p>
            <p>Accesorios: 5 piezas incluidas</p>
            <p>Peso: 108 gr (Aprox)</p>
            <p>Color: Negro con…</p>
            <p>Presentación: Individual, caja diseño kraft</p>
        </div>
    </article>
    """

    product = CategoryProductExtractor().extract(BeautifulSoup(html, "lxml"))

    assert "Medidas: 6 cm x 9.6 cm x 2.2 cm (Aprox)" in product.description
    assert "Material: Bambú y ABS" in product.description
    assert "Funciones: 7 funciones" in product.description
    assert "Accesorios: 5 piezas incluidas" in product.description
    assert "Peso: 108 gr (Aprox)" in product.description
    assert "Presentación: Individual, caja diseño kraft" in product.description
    assert "Color:" not in product.description


def test_color_only_text_content_does_not_hide_visible_multiblock_detail():
    html = """
    <article>
        <p class="brxe-a26f34">FB-5016</p>
        <h2 class="brxe-f31760">Wincha Multiherramienta Eliza 3m</h2>
        <div class="text-content">Color: Negro con…</div>
        <div class="brxe-text-basic">
            <p>Medidas: 6 cm x 9.6 cm x 2.2 cm (Aprox)</p>
            <p>Material: Bambú y ABS</p>
            <p>Funciones: 7 funciones (cinta métrica de 3 m, destornillador con puntas planas, philips y allen, nivel integrado)</p>
            <p>Accesorios: 5 piezas incluidas</p>
            <p>Peso: 108 gr (Aprox)</p>
            <p>Presentación: Individual, caja diseño kraft</p>
        </div>
    </article>
    """

    product = CategoryProductExtractor().extract(BeautifulSoup(html, "lxml"))

    assert "Medidas: 6 cm x 9.6 cm x 2.2 cm (Aprox)" in product.description
    assert "Material: Bambú y ABS" in product.description
    assert "Funciones: 7 funciones" in product.description
    assert "Accesorios: 5 piezas incluidas" in product.description
    assert "Peso: 108 gr (Aprox)" in product.description
    assert "Presentación: Individual, caja diseño kraft" in product.description
    assert "Color:" not in product.description


def test_empty_text_content_does_not_fall_back_to_unrelated_blocks():
    html = (
        '<article><p class="brxe-a26f34">TEST-002</p>'
        '<h2 class="brxe-f31760">Producto sin detalle</h2>'
        '<div class="text-content"></div>'
        '<div class="brxe-text-basic">Material: ABS. Dimensiones: 10 x 5 cm. '
        'Este texto no pertenece al campo Detalle.</div></article>'
    )
    product = CategoryProductExtractor().extract(BeautifulSoup(html, "lxml"))
    assert product.code == "TEST-002"
    assert product.description == ""


def test_category_product_extractor_keeps_valid_sibling_fields_around_an_empty_detail_attribute():
    html = """
    <article>
        <p class="brxe-a26f34">TEST-001</p>
        <h2 class="brxe-f31760">Producto de prueba</h2>
        <div class="text-content">Empaque Individual:</div>
        <div class="brxe-text-basic">
            <p>Color: Negro.</p>
            <p>Material: Poliester.</p>
            <p>Dimensiones: 15.5*3cm.</p>
            <p>Peso Unitario: 2 G.</p>
            <p>Uso Recomendado: Estuche para bolígrafos.</p>
            <p>Cantidad Por Caja: 5000 Pza.</p>
            <p>Dimensiones Caja: 37*33*25cm.</p>
            <p>Cubicaje por Caja: 0.030525 m³/CBM.</p>
            <p>Peso neto por caja: 10 Kg.</p>
            <p>Peso bruto por caja: 11 Kg.</p>
        </div>
    </article>
    """

    product = CategoryProductExtractor().extract(BeautifulSoup(html, "lxml"))

    assert product.code == "TEST-001"
    assert "Empaque Individual: Material: Poliester." in product.description
    assert "Material: Poliester." in product.description
    assert "Dimensiones: 15.5*3cm." in product.description
    assert "Peso Unitario: 2 G." in product.description
    assert "Uso Recomendado: Estuche para bolígrafos." in product.description
    assert "Cantidad Por Caja: 5000 Pza." in product.description
    assert "Dimensiones Caja: 37*33*25cm." in product.description
    assert "Cubicaje por Caja: 0.030525 m³/CBM." in product.description
    assert "Peso neto por caja: 10 Kg." in product.description
    assert "Peso bruto por caja: 11 Kg." in product.description
    assert "Color:" not in product.description


def test_empty_fallback_detail_attribute_does_not_become_description():
    html = """
    <article>
        <p class="brxe-a26f34">TEST-003</p>
        <h2 class="brxe-f31760">Producto sin atributos informados</h2>
        <div class="brxe-text-basic">
            <p>Empaque Individual:</p>
        </div>
    </article>
    """

    product = CategoryProductExtractor().extract(BeautifulSoup(html, "lxml"))

    assert product.code == "TEST-003"
    assert product.description == ""


def test_category_product_extractor_preserves_hl_3000_marketing_copy():
    detail = (
        "Amplía tus opciones de estilo con nuestro Gorro Sublimable. "
        "Este versátil gorro te permite personalizarlo con tus diseños, "
        "imágenes o logotipos favoritos, lo que lo convierte en una excelente "
        "elección para destacar tu individualidad o promocionar tu marca."
    )
    html = (
        '<article><p class="brxe-a26f34">HL-3000</p>'
        '<h2 class="brxe-f31760">Gorro Sublimable</h2>'
        f'<div class="text-content">{detail}</div></article>'
    )
    product = CategoryProductExtractor().extract(BeautifulSoup(html, "lxml"))
    assert product.code == "HL-3000"
    assert product.description == detail


def test_category_product_extractor_does_not_use_short_generic_prose_as_detail():
    html = """
    <article>
        <p class="brxe-a26f34">FB-1235</p>
        <h2 class="brxe-f31760">Producto completo</h2>
        <div class="text-content">Descripción promocional general.</div>
    </article>
    """
    product = CategoryProductExtractor().extract(BeautifulSoup(html, "lxml"))

    assert product.code == "FB-1235"
    assert product.description == ""





def test_category_product_extractor_keeps_only_date_label_bold_and_unbolds_standalone_punctuation():
    html = """
    <article>
        <p class="brxe-a26f34">TEST-BOLD-VALUE-BOUNDARIES</p>
        <h2 class="brxe-f31760">Producto de prueba</h2>
        <div class="text-content">
            <ul>
                <li><strong>Fecha: <span style="color: red">2026 \u2013 2027</span></strong></li>
                <li><strong>Medida: </strong>23.5x32cm<strong>.</strong></li>
                <li><strong>Técnica de aplicación</strong>: Serigrafía</li>
            </ul>
        </div>
    </article>
    """

    product = CategoryProductExtractor().extract(
        BeautifulSoup(html, "lxml")
    )

    assert product.description.splitlines() == [
        "Fecha: 2026 \u2013 2027",
        "Medida: 23.5x32cm.",
        "Técnica de aplicación: Serigrafía",
    ]

    assert (
        "<strong>Fecha:</strong> <span>2026 \u2013 2027</span>"
        in product.description_html
    )
    assert "<strong>Medida: </strong>23.5x32cm." in product.description_html
    assert "<strong>.</strong>" not in product.description_html

    # A source label whose colon is outside the emphasis remains unchanged.
    assert (
        "<strong>Técnica de aplicación</strong>: Serigrafía"
        in product.description_html
    )
    assert detail_html_matches_text(
        product.description_html,
        product.description,
    )

def test_category_product_extractor_repairs_only_missing_space_after_bold_field_labels():
    html = """
    <article>
        <p class="brxe-a26f34">TEST-BOLD-SPACING</p>
        <h2 class="brxe-f31760">Producto de prueba</h2>
        <div class="text-content">
            <ul>
                <li><strong>Empaque Individual:</strong>Bolsa plástica transparente.</li>
                <li><strong>Material:</strong><span>ABS</span>.</li>
                <li><strong>Medidas</strong>:7.5 cm.</li>
                <li><strong>Fecha: </strong>2026 \u2013 2027.</li>
                <li><strong>Descripción:</strong> texto <em>con</em>catenado.</li>
            </ul>
        </div>
    </article>
    """

    product = CategoryProductExtractor().extract(
        BeautifulSoup(html, "lxml")
    )

    assert product.description.splitlines() == [
        "Empaque Individual: Bolsa plástica transparente.",
        "Material: ABS.",
        "Medidas: 7.5 cm.",
        "Fecha: 2026 \u2013 2027.",
        "Descripción: texto concatenado.",
    ]

    rendered = BeautifulSoup(product.description_html, "lxml")
    items = rendered.select("li")
    assert len(items) == 5
    assert items[0].get_text("", strip=False) == (
        "Empaque Individual: Bolsa plástica transparente."
    )
    assert items[1].get_text("", strip=False) == "Material: ABS."
    assert items[2].get_text("", strip=False) == "Medidas: 7.5 cm."
    assert items[3].get_text("", strip=False) == "Fecha: 2026 \u2013 2027."
    assert items[4].get_text("", strip=False) == "Descripción: texto concatenado."
    assert "<strong>Empaque Individual:</strong> Bolsa" in product.description_html
    assert "<strong>Material:</strong> <span>ABS</span>" in product.description_html
    assert "<strong>Medidas</strong>: 7.5 cm." in product.description_html
    assert "<strong>Fecha: </strong>2026 \u2013 2027." in product.description_html
    assert "<em>con</em>catenado." in product.description_html
    assert detail_html_matches_text(
        product.description_html,
        product.description,
    )

def test_category_product_extractor_preserves_source_strong_and_bold_labels_as_rich_html():
    html = """
    <article>
        <p class="brxe-a26f34">HL-9400</p>
        <h2 class="brxe-f31760">Set de Escritorio Pote</h2>
        <div class="text-content">
            <ul>
                <li><strong>Medidas:</strong> 7.5 x 7 cm. (Aprox.)</li>
                <li><b>Descripción:</b> Pote de plástico traslúcido que contiene:
                    1 Saca grapas, 1 Engrapadora, repuestos, 1 Cinta Adhesiva,
                    1 Perforadora de un hueco.</li>
                <li><strong>Presentación del Producto:</strong>
                    Individual, en bolsa de plástico transparente.</li>
            </ul>
        </div>
    </article>
    """

    product = CategoryProductExtractor().extract(
        BeautifulSoup(html, "lxml")
    )

    assert product.code == "HL-9400"
    assert product.description.splitlines() == [
        "Medidas: 7.5 x 7 cm. (Aprox.)",
        (
            "Descripción: Pote de plástico traslúcido que contiene: "
            "1 Saca grapas, 1 Engrapadora, repuestos, 1 Cinta Adhesiva, "
            "1 Perforadora de un hueco."
        ),
        (
            "Presentación del Producto: Individual, en bolsa de plástico "
            "transparente."
        ),
    ]
    assert "<strong>Medidas:</strong>" in product.description_html
    assert "<b>Descripción:</b>" in product.description_html
    assert "<strong>Presentación del Producto:</strong>" in product.description_html
    assert detail_html_matches_text(
        product.description_html,
        product.description,
    )
