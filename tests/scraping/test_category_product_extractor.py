from bs4 import BeautifulSoup

from scrapers.extractors.category_product_extractor import (
    CategoryProductExtractor,
)


def test_category_product_extractor_maps_stock_to_colors():
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

    assert product.color_stock == {
        "Dorado": 6646,
        "Plateado": 7942,
    }
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

    assert product.color_stock == {
        "Amarillo": 1520,
        "Azul": 0,
        "Blanco": 20,
    }
    assert product.stock == 1540


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
    assert product.price_sample == 8.0
    assert product.price_hundred == 16.0
    assert product.price_thousand == 152.0
