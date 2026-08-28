from bs4 import BeautifulSoup

from scrapers.extractors.category_extractor import CategoryExtractor


def test_duplicate_category_links_merge_published_count():
    html = """
    <nav>
        <a href="/categoria-producto/papeles-fotograficos/">
            Papeles Fotográficos
        </a>
    </nav>
    <section>
        <div class="category-card">
            <span>Producto(s) 82</span>
            <h3>Papeles Fotográficos</h3>
            <a href="/categoria-producto/papeles-fotograficos/">
                Ver Categoría
            </a>
        </div>
    </section>
    """

    categories = CategoryExtractor().extract(BeautifulSoup(html, "html.parser"))

    assert len(categories) == 1
    assert categories[0].name == "Papeles Fotográficos"
    assert categories[0].expected_count == 82


def test_duplicate_category_links_keep_nonzero_count():
    html = """
    <section>
        <div>
            <span>Producto(s) 50</span>
            <h3>Artículos Antiestrés</h3>
            <a href="/categoria-producto/antiestres/">Ver Categoría</a>
        </div>
        <nav>
            <a href="/categoria-producto/antiestres/">Artículos Antiestrés</a>
        </nav>
    </section>
    """

    categories = CategoryExtractor().extract(BeautifulSoup(html, "html.parser"))

    assert len(categories) == 1
    assert categories[0].expected_count == 50
