from bs4 import BeautifulSoup

from scrapers.extractors.stock_extractor import StockExtractor


def test_stock_extractor_extracts_available_stock():

    html = """
    <div>
        Stock Disponible 25
    </div>
    """

    soup = BeautifulSoup(
        html,
        "html.parser",
    )

    extractor = StockExtractor()

    result = extractor.extract(soup)

    assert result == 25
