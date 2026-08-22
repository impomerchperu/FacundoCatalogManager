from bs4 import BeautifulSoup

from scrapers.extractors.product_card_extractor import ProductCardExtractor


def test_prefers_product_table_rows_over_limited_visual_cards():
    html = """
    <div class="jsfb-filterable">
        <h2>Producto visual limitado</h2>
        <a href="/producto/visual/"><img src="visual.jpg"></a>
    </div>
    <table>
        <thead>
            <tr><th>Código</th><th>Producto(s)</th></tr>
        </thead>
        <tbody>
            <tr>
                <td>F320</td>
                <td>
                    <a href="/producto/maquina-f320/">
                        <h2>Maquina F320</h2>
                    </a>
                </td>
            </tr>
            <tr>
                <td>F110</td>
                <td>
                    <a href="/producto/maquina-f110/">
                        <h2>Maquina F110</h2>
                    </a>
                </td>
            </tr>
        </tbody>
    </table>
    """

    soup = BeautifulSoup(html, "lxml")
    cards = ProductCardExtractor().extract(soup)

    assert len(cards) == 2
    assert cards[0].select_one('a[href*="/producto/"]')["href"] == (
        "/producto/maquina-f320/"
    )
    assert cards[1].select_one('a[href*="/producto/"]')["href"] == (
        "/producto/maquina-f110/"
    )


def test_falls_back_to_visual_cards_when_product_table_is_absent():
    html = """
    <div class="jsfb-filterable">
        <a href="/producto/visual/"><h2>Producto visual</h2></a>
    </div>
    """

    soup = BeautifulSoup(html, "lxml")

    assert len(ProductCardExtractor().extract(soup)) == 1
