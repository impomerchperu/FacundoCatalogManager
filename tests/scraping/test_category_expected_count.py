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
