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


def test_price_extractor_recovers_prices_without_price_classes():
    html = """
    <article>
        <h3>Precio Muestra</h3>
        <div>S/ 8.00</div>
        <span>Menos de 50 unidades</span>
        <h3>Precio Ciento</h3>
        <div>S/ 670.00</div>
        <span>A partir de 50 unidades</span>
        <h3>Precio Millar</h3>
        <div>S/ 6500.00</div>
        <span>A partir de 500 unidades</span>
    </article>
    """

    soup = BeautifulSoup(html, "lxml")
    extractor = PriceExtractor()

    assert extractor.extract_sample(soup) == 8.0
    assert extractor.extract_hundred(soup) == 670.0
    assert extractor.extract_thousand(soup) == 6500.0


def test_price_extractor_recovers_bricks_table_row_prices():
    html = """
    <table>
        <tbody>
            <tr class="jsfb-filterable">
                <td><span class="sku">FB-5013</span></td>
                <td><h2>Memo Clip Cubo</h2></td>
                <td><div class="variaciones-producto"><p>2</p></div></td>
                <td>
                    <h3>S/ 2.50</h3>
                    <p>Menos de<br>50 unidades</p>
                </td>
                <td>
                    <h4>S/ 180.00</h4>
                    <p>A partir de<br>50 unidades</p>
                </td>
                <td>
                    <h4>S/ 1600.00</h4>
                    <p>A partir de<br>500 unidades</p>
                </td>
            </tr>
        </tbody>
    </table>
    """

    soup = BeautifulSoup(html, "lxml")
    row = soup.select_one("tr")
    extractor = PriceExtractor()

    assert extractor.extract_sample(row) == 2.5
    assert extractor.extract_hundred(row) == 180.0
    assert extractor.extract_thousand(row) == 1600.0


def test_price_extractor_recovers_table_prices_from_flexible_cell_markup():
    html = """
    <table>
        <tbody>
            <tr class="jsfb-filterable">
                <td>FB-5014</td>
                <td><h2>Producto de prueba</h2></td>
                <td>Stock 10</td>
                <td>
                    <div>S/ 8.00</div>
                    <span>Menos de 50 unidades</span>
                </td>
                <td>
                    <div>S/ 670.00</div>
                    <span>A partir de 50 unidades</span>
                </td>
                <td>
                    <div>S/ 6500.00</div>
                    <span>A partir de 500 unidades</span>
                </td>
            </tr>
        </tbody>
    </table>
    """

    soup = BeautifulSoup(html, "lxml")
    row = soup.select_one("tr")
    extractor = PriceExtractor()

    assert extractor.extract_sample(row) == 8.0
    assert extractor.extract_hundred(row) == 670.0
    assert extractor.extract_thousand(row) == 6500.0
