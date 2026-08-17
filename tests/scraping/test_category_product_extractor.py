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


def test_category_product_extractor_recovers_alternate_code_class():
    html = """
    <article>
        <span class="sku">PS-1100</span>
        <h2 class="brxe-f31760">Producto alternativo</h2>
    </article>
    """

    card = BeautifulSoup(html, "lxml")

    assert CategoryProductExtractor().extract(card).code == "PS-1100"


def test_category_product_extractor_recovers_code_from_card_text():
    html = """
    <article>
        <h2 class="brxe-f31760">Producto SKB05X-1</h2>
        <div class="text-content">Detalle sin selector SKU.</div>
    </article>
    """

    card = BeautifulSoup(html, "lxml")

    assert CategoryProductExtractor().extract(card).code == "SKB05X-1"


def test_category_product_extractor_rejects_unrelated_model_text():
    html = """
    <article>
        <h2 class="brxe-f31760">Modelo 8274A</h2>
    </article>
    """

    card = BeautifulSoup(html, "lxml")

    assert CategoryProductExtractor().extract(card).code == ""
