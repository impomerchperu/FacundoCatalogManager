from bs4 import BeautifulSoup

from scrapers.extractors.category_extractor import CategoryExtractor


def test_category_extractor_reads_count_before_matching_heading():
    html = """
    <section>
        <div class="category-card">
            <span>Producto(s) 50</span>
            <h3>Artículos Antiestrés</h3>
            <a href="/categoria-producto/articulos-antiestres/">Ver Categoría</a>
        </div>
        <div class="category-card">
            <span>Producto(s) 31</span>
            <h3>Artículos de Escritorio</h3>
            <a href="/categoria-producto/articulos-escritorio/">Ver Categoría</a>
        </div>
    </section>
    """

    categories = CategoryExtractor().extract(BeautifulSoup(html, "html.parser"))

    assert [(category.name, category.expected_count) for category in categories] == [
        ("Artículos Antiestrés", 50),
        ("Artículos de Escritorio", 31),
    ]


def test_category_extractor_does_not_use_previous_category_count():
    html = """
    <section>
        <div class="category-card">
            <span>Producto(s) 50</span>
            <h3>Primera</h3>
            <a href="/categoria-producto/primera/">Ver Categoría</a>
        </div>
        <div class="category-card">
            <span>Producto(s) 7</span>
            <h3>Segunda</h3>
            <a href="/categoria-producto/segunda/">Ver Categoría</a>
        </div>
    </section>
    """

    categories = CategoryExtractor().extract(BeautifulSoup(html, "html.parser"))

    assert [category.expected_count for category in categories] == [50, 7]
