from bs4 import BeautifulSoup

from scrapers.extractors.price_extractor import PriceExtractor
from scrapers.extractors.product_extractor import ProductExtractor


def test_price_extractor_distinguishes_decimal_comma_from_thousands_comma():
    extractor = PriceExtractor()

    assert extractor._parse_price("8,50") == 8.5
    assert extractor._parse_price("1,250") == 1250.0
    assert extractor._parse_price("12,500") == 12500.0
    assert extractor._parse_price("1,250,000") == 1250000.0


def test_product_extractor_uses_consistent_price_parser_for_fallback_price():
    html = """
    <article>
        <span class="product-price">S/ 8,50</span>
        <h1>Producto con precio decimal</h1>
    </article>
    """

    soup = BeautifulSoup(html, "lxml")
    result = ProductExtractor().extract(soup)

    assert result["price"] == 8.5
