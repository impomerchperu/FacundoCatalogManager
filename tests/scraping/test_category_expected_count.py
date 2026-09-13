from bs4 import BeautifulSoup

from scrapers.extractors.category_extractor import CategoryExtractor


def test_category_extractor_reads_expected_count_from_deeply_nested_block():
    html = """
    <section class="category-card">
        <div class="nested-wrapper">
            <div class="category-info">
                <span>Producto(s) 79</span>
                <h3>Papelería Grafipapel</h3>
                <div class="cta">
                    <a href="/categoria-producto/papeleria-grafipapel/">
                        Ver Categoría
                    </a>
                </div>
            </div>
        </div>
    </section>
    """

    soup = BeautifulSoup(html, "html.parser")
    categories = CategoryExtractor().extract(soup)

    assert categories[0].name == "Papelería Grafipapel"
    assert categories[0].expected_count == 79


def test_category_extractor_matches_mojibake_category_heading_for_expected_count():
    html = """
    <section>
        <h3>Articulos De Antiestres</h3>
        <span>Producto(s) 50</span>
        <div>
            <a href="/categoria-producto/articulos-de-antiestres/">Ver Categoría</a>
        </div>
    </section>
    """
    categories = CategoryExtractor().extract(BeautifulSoup(html, "html.parser"))
    assert categories[0].name == "Articulos De Antiestres"
    assert categories[0].expected_count == 50


def test_category_extractor_matches_accented_and_mojibake_category_variants():
    html = """
    <section>
        <h3>ArtÃculos AntiestrÃ©s</h3>
        <span>Producto(s) 50</span>
        <div>
            <a href="/categoria-producto/articulos-de-antiestres/">Ver Categoría</a>
        </div>
    </section>
    """
    categories = CategoryExtractor().extract(BeautifulSoup(html, "html.parser"))
    assert categories[0].name == "ArtÃculos AntiestrÃ©s"
    assert categories[0].expected_count == 50


def test_category_extractor_merges_same_category_url_and_keeps_highest_count():
    html = """
    <div>
        <h2>Nuestras Categorías</h2>
        <section>
            <h3>Articulos De Antiestres</h3>
            <span>Producto(s) 25</span>
            <a href="/categoria-producto/articulos-de-antiestres/">Ver Categoría</a>
        </section>
        <section>
            <h3>ArtÃculos AntiestrÃ©s</h3>
            <span>Producto(s) 50</span>
            <a href="/categoria-producto/articulos-de-antiestres/">Ver Categoría</a>
        </section>
    </div>
    """

    categories = CategoryExtractor().extract(BeautifulSoup(html, "html.parser"))

    antiestres = [
        category
        for category in categories
        if category.url.endswith("/articulos-de-antiestres/")
    ]

    assert len(antiestres) == 1
    assert antiestres[0].expected_count == 50
    assert antiestres[0].name == "Articulos De Antiestres"
