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
