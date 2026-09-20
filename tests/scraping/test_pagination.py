from bs4 import BeautifulSoup

from scrapers.pagination import PaginationExtractor


def test_get_next_page():
    html = """
    <a class="next"
       href="/categoria/page/2">
       Siguiente
    </a>
    """

    soup = BeautifulSoup(html, "lxml")
    result = PaginationExtractor().get_next_page(soup)

    assert result == "/categoria/page/2"
