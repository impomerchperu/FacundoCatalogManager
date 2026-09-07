from bs4 import BeautifulSoup

from scrapers.extractors.category_extractor import CategoryExtractor


def test_category_extractor_reads_count_from_deeply_nested_category_block():
    nested = '<a href="/categoria-producto/papeleria/">Ver Categoría</a>'
    for _ in range(12):
        nested = f"<div>{nested}</div>"
    html = f"""
    <section>
        <h3>Papelería Grafipapel</h3>
        <span>Producto(s) 79</span>
        {nested}
    </section>
    """

    categories = CategoryExtractor().extract(BeautifulSoup(html, "html.parser"))

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
