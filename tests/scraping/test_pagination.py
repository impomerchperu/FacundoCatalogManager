from scrapers.pagination import PaginationExtractor
from scrapers.parser import Parser


def test_get_next_page():

    html = """
    <a class="next"
       href="/categoria/page/2">
       Siguiente
    </a>
    """

    soup = Parser().parse(html)

    extractor = PaginationExtractor()

    result = extractor.get_next_page(soup)

    assert result == "/categoria/page/2"
