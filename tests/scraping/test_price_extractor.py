from bs4 import BeautifulSoup

from scrapers.extractors.price_extractor import PriceExtractor


def test_price_extractor_reads_category_price_blocks():
    html = """
    <article>
        <div class="content-precio">
            <h3>Precio Muestra</h3>
            <h4>S/ 8.50</h4>
            <p>Menos de 50 unidades</p>
        </div>
        <div class="content-precio">
            <h3>Precio Ciento</h3>
            <h4>S/ 770.00</h4>
            <p>A partir de 50 unidades</p>
        </div>
        <div class="content-precio">
            <h3>Precio Millar</h3>
            <h4>S/ 7500.00</h4>
            <p>A partir de 500 unidades</p>
        </div>
    </article>
    """

    soup = BeautifulSoup(html, "lxml")
    extractor = PriceExtractor()

    assert extractor.extract_sample(soup) == 8.5
    assert extractor.extract_hundred(soup) == 770.0
    assert extractor.extract_thousand(soup) == 7500.0


def test_price_extractor_accepts_decimal_comma():
    html = """
    <div class="content-precio">
        <h3>Precio Muestra</h3>
        <h4>S/ 8,50</h4>
    </div>
    """

    soup = BeautifulSoup(html, "lxml")

    assert PriceExtractor().extract_sample(soup) == 8.5


def test_price_extractor_keeps_legacy_heading_structure():
    html = """
    <article>
        <h3>Precio Muestra</h3>
        <h4>S/ 6.50</h4>
    </article>
    """

    soup = BeautifulSoup(html, "lxml")

    assert PriceExtractor().extract_sample(soup) == 6.5
