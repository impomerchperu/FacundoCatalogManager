from bs4 import BeautifulSoup

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


def test_category_product_extractor_recognizes_sublimation_fields():
    html = """
    <article>
        <p class="brxe-a26f34">FB-2003</p>
        <h2 class="brxe-f31760">Jarrito de Cerámica</h2>
        <div class="text-content">
            Medida y capacidad: 10.5 cm x 8.5 cm – 444 ml.
            Medida de impresión: 21 x 11 cm.
            Calidad: AAA, alta calidad.
            Material: Cerámica blanca.
        </div>
    </article>
    """

    product = CategoryProductExtractor().extract(BeautifulSoup(html, "lxml"))

    assert "Medida y capacidad: 10.5 cm x 8.5 cm – 444 ml" in product.description
    assert "Medida de impresión: 21 x 11 cm" in product.description
    assert "Calidad: AAA, alta calidad" in product.description
    assert "Material: Cerámica blanca" in product.description


def test_category_product_extractor_rejects_detail_with_empty_final_field():
    html = """
    <article>
        <p class="brxe-a26f34">FB-7080</p>
        <h2 class="brxe-f31760">Laminado A4</h2>
        <div class="text-content">Medida: A4. Paquete: 20 Unidades. Caja:</div>
    </article>
    """

    product = CategoryProductExtractor().extract(BeautifulSoup(html, "lxml"))

    assert product.description == "Medida: A4. Paquete: 20 Unidades"


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


def test_category_product_extractor_rejects_explicit_description_prefix():
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

    assert product.description == ""


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
