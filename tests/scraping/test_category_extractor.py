from bs4 import BeautifulSoup

from scrapers.extractors.category_extractor import CategoryExtractor


def test_extract_categories():

    html = """
    <ul class="product-categories">

        <li>
            <a href="/categoria-producto/jarros-mug/">
                Jarros Mug
            </a>
        </li>

        <li>
            <a href="/categoria-producto/termos/">
                Termos
            </a>
        </li>

    </ul>
    """

    soup = BeautifulSoup(html, "lxml")

    extractor = CategoryExtractor()

    categories = extractor.extract(soup)

    assert len(categories) == 2

    assert categories[0].name == "Jarros Mug"

    assert categories[0].url == "/categoria-producto/jarros-mug/"
