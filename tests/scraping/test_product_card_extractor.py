from bs4 import BeautifulSoup

from scrapers.extractors.product_card_extractor import ProductCardExtractor


def test_prefers_price_bearing_visual_cards_over_product_table():
    html = """
    <div class="jsfb-filterable">
        <a href="/producto/jarro/"><h2>Jarro Mug</h2></a>
        <div class="content-precio">
            <h3>Precio Muestra</h3><h4>S/ 8.00</h4>
        </div>
        <div class="content-precio">
            <h3>Precio Ciento</h3><h4>S/ 670.00</h4>
        </div>
        <div class="content-precio">
            <h3>Precio Millar</h3><h4>S/ 6500.00</h4>
        </div>
    </div>
    <table><tbody>
        <tr><td><a href="/producto/jarro/">Jarro Mug</a></td></tr>
    </tbody></table>
    """

    soup = BeautifulSoup(html, "lxml")
    cards = ProductCardExtractor().extract(soup)

    assert len(cards) == 1
    assert cards[0].get("class") == ["jsfb-filterable"]
    assert cards[0].select_one(".content-precio") is not None


def test_prefers_visual_cards_when_table_is_also_present():
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

    assert len(cards) == 1
    assert cards[0].select_one('a[href*="/producto/"]')["href"] == (
        "/producto/visual/"
    )


def test_prefers_visual_cards_when_mixed_with_missing_prices():
    html = """
    <div class="jsfb-filterable">
        <a href="/producto/con-precio/"><h2>Producto con precio</h2></a>
        <div class="content-precio">
            <h3>Precio Muestra</h3><h4>S/ 8.00</h4>
        </div>
    </div>
    <div class="jsfb-filterable">
        <a href="/producto/sin-precio/"><h2>Producto sin precio</h2></a>
    </div>
    <table>
        <tbody>
            <tr>
                <td><a href="/producto/con-precio/">Producto con precio</a></td>
            </tr>
            <tr>
                <td><a href="/producto/sin-precio/">Producto sin precio</a></td>
            </tr>
        </tbody>
    </table>
    """

    soup = BeautifulSoup(html, "lxml")
    cards = ProductCardExtractor().extract(soup)

    assert len(cards) == 2
    assert [card.select_one('a[href*="/producto/"]')["href"] for card in cards] == [
        "/producto/con-precio/",
        "/producto/sin-precio/",
    ]


def test_falls_back_to_visual_cards_when_product_table_is_absent():
    html = """
    <div class="jsfb-filterable">
        <a href="/producto/visual/"><h2>Producto visual</h2></a>
    </div>
    """

    soup = BeautifulSoup(html, "lxml")

    assert len(ProductCardExtractor().extract(soup)) == 1


def test_falls_back_to_jsfb_cards_when_default_card_selector_matches_none():
    html = """
    <div class="jsfb-filterable">
        <a href="/producto/page-two/"><h2>Producto pagina dos</h2></a>
    </div>
    """

    soup = BeautifulSoup(html, "lxml")

    cards = ProductCardExtractor().extract(soup)

    assert len(cards) == 1
    assert cards[0].get("class") == ["jsfb-filterable"]
    assert cards[0].select_one('a[href*="/producto/"]')["href"] == (
        "/producto/page-two/"
    )
