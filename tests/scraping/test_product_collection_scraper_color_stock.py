from models.scraping.category import Category
from scrapers.collectors.product_collection_scraper import (
    ProductCollectionScraper,
)
from scrapers.extractors.category_product_extractor import (
    CategoryProductExtractor,
)
from scrapers.extractors.product_extractor import ProductExtractor


class FakeCategoryScraper:
    def get_category_pages(self, url):
        return [url]

    def get_html(self, url):
        if "/producto/" in url:
            return """
            <html>
                <h1>Pelota Antiestrés 6.3 cm</h1>
                <p class="brxe-heading">FB-4001-D</p>
                <div>
                    Colores
                    <a href="/color/dorado">Dorado</a>
                    <a href="/color/plateado">Plateado</a>
                </div>
            </html>
            """
        return """
        <html>
            <article class="jsfb-filterable">
                <a href="/producto/pelota-antiestres-6-3-cm-2/">
                    <h2 class="brxe-f31760">Pelota Antiestrés 6.3 cm</h2>
                </a>
                <p class="brxe-a26f34">FB-4001-D</p>
                <div class="variaciones-producto">
                    <p>6646</p>
                    <p>7942</p>
                </div>
            </article>
        </html>
        """


def test_collection_scraper_preserves_total_stock_when_detail_has_only_color_names():
    scraper = ProductCollectionScraper(
        FakeCategoryScraper(),
        card_extractor=lambda soup: [soup.select_one("article")],
        product_extractor=CategoryProductExtractor(),
        detail_extractor=ProductExtractor(),
    )

    products = scraper.scrape_category(
        Category(
            name="Artículos Antiestrés",
            url="https://example.com/categoria/",
        ),
    )

    assert len(products) == 1
    assert products[0].color_stock == {}
    assert products[0].stock == 14588


class FakeSpanishColorCategoryScraper:
    def get_category_pages(self, url):
        return [url]

    def get_html(self, url):
        if "/producto/" in url:
            return """
            <html>
                <h1>Producto por colores</h1>
                <p class="brxe-heading">FB-5000</p>
                <div>Colores: Amarillo, Azul, Blanco</div>
            </html>
            """
        return """
        <html>
            <article class="jsfb-filterable">
                <a href="/producto/producto-por-colores/">
                    <h2 class="brxe-f31760">Producto por colores</h2>
                </a>
                <p class="brxe-a26f34">FB-5000</p>
                <div class="text-content">
                    Colores: Rojo, Verde, Negro
                    Stock Disponible 1520 0 20
                </div>
            </article>
        </html>
        """


def test_collection_scraper_uses_detail_colors_for_card_stock_values():
    scraper = ProductCollectionScraper(
        FakeSpanishColorCategoryScraper(),
        card_extractor=lambda soup: [soup.select_one("article")],
        product_extractor=CategoryProductExtractor(),
        detail_extractor=ProductExtractor(),
    )

    products = scraper.scrape_category(
        Category(
            name="Artículos por colores",
            url="https://example.com/categoria/",
        ),
    )

    assert len(products) == 1
    assert products[0].color_stock == {}
    assert products[0].stock == 1540


class FakeDetailVariationCategoryScraper:
    def get_category_pages(self, url):
        return [url]

    def get_html(self, url):
        if "/producto/" in url:
            return """
            <html>
                <h1>Producto por colores</h1>
                <p class="brxe-heading">FB-4009-AM</p>
                <form class="variations_form" data-product_variations='[
                    {"attributes":{"attribute_pa_color":"amarillo"},"max_qty":1520},
                    {"attributes":{"attribute_pa_color":"azul"},"max_qty":0},
                    {"attributes":{"attribute_pa_color":"blanco"},"max_qty":20}
                ]'>
                    <select name="attribute_pa_color">
                        <option value="amarillo">Amarillo</option>
                        <option value="azul">Azul</option>
                        <option value="blanco">Blanco</option>
                    </select>
                </form>
            </html>
            """
        return """
        <html>
            <article class="jsfb-filterable">
                <a href="/producto/producto-por-colores/">
                    <h2 class="brxe-f31760">Producto por colores</h2>
                </a>
                <p class="brxe-a26f34">FB-4009-AM</p>
                <div class="variaciones-producto">
                    <p>1540</p>
                </div>
            </article>
        </html>
        """


def test_collection_scraper_reads_detail_variation_stock_when_card_has_total_only():
    scraper = ProductCollectionScraper(
        FakeDetailVariationCategoryScraper(),
        card_extractor=lambda soup: [soup.select_one("article")],
        product_extractor=CategoryProductExtractor(),
        detail_extractor=ProductExtractor(),
    )

    products = scraper.scrape_category(
        Category(
            name="Artículos por colores",
            url="https://example.com/categoria/",
        ),
    )

    assert len(products) == 1
    assert products[0].color_stock == {
        "Amarillo": 1520,
        "Azul": 0,
        "Blanco": 20,
    }
    assert products[0].stock == 1540


def test_category_extractor_maps_real_description_colors_to_stock_values():
    html = """
    <article>
        <a href="/producto/lapicero/">
            <h2 class="brxe-f31760">Lapicero Metálico</h2>
        </a>
        <p class="brxe-a26f34">FB-2200</p>
        <div class="text-content">
            Colores: Rojo, Negro, Azul, Gris Gun, y Silver.
        </div>
        <div class="variaciones-producto">
            <p>100</p>
            <p>200</p>
            <p>300</p>
            <p>400</p>
            <p>500</p>
        </div>
    </article>
    """

    from bs4 import BeautifulSoup

    card = BeautifulSoup(html, "lxml").select_one("article")
    result = CategoryProductExtractor().extract(card)

    assert result.color_stock == {}
    assert result.stock == 1500


def test_category_extractor_reads_colores_de_tinta_and_numeric_label():
    html = """
    <article>
        <h2 class="brxe-f31760">Resaltador</h2>
        <p class="brxe-a26f34">FB-1319</p>
        <div class="text-content">
            Colores de tinta: Fucsia, amarillo, verde y celeste
        </div>
        <div class="variaciones-producto">
            <p>10</p>
            <p>20</p>
            <p>30</p>
            <p>40</p>
        </div>
    </article>
    """

    from bs4 import BeautifulSoup

    card = BeautifulSoup(html, "lxml").select_one("article")
    result = CategoryProductExtractor().extract(card)

    assert result.color_stock == {}
    assert result.stock == 100


def test_category_extractor_reads_disponible_en_colores_without_colon():
    html = """
    <article>
        <h2 class="brxe-f5021">Regla Plástica 20 cm</h2>
        <p class="brxe-a26f34">FB-5021</p>
        <div class="text-content">
            Propiedades: disponible en colores azul, rojo y blanco.
            Presentación: Individual en bolsa plástica transparente.
        </div>
        <div class="variaciones-producto">
            <p>0</p>
            <p>0</p>
            <p>0</p>
        </div>
    </article>
    """

    from bs4 import BeautifulSoup

    card = BeautifulSoup(html, "lxml").select_one("article")
    result = CategoryProductExtractor().extract(card)

    assert result.color_stock == {}
    assert result.stock == 0


def test_category_extractor_reads_colores_disponibles_and_maps_stock():
    html = """
    <article>
        <h2 class="brxe-f6002">Mochilas de Lona</h2>
        <p class="brxe-a26f34">FB-6002</p>
        <div class="text-content">
            Colores disponibles: Azul, Rojo, Negro, Gris
            Presentación: Individual en bolsa.
        </div>
        <div class="variaciones-producto">
            <p>528</p>
            <p>124</p>
            <p>1686</p>
            <p>355</p>
        </div>
    </article>
    """

    from bs4 import BeautifulSoup

    card = BeautifulSoup(html, "lxml").select_one("article")
    result = CategoryProductExtractor().extract(card)

    assert result.color_stock == {}
    assert result.stock == 2693


def test_category_extractor_does_not_guess_disponible_en_colores_stock():
    html = """
    <article>
        <h2 class="brxe-f5021">Regla Plástica 20 cm</h2>
        <p class="brxe-a26f34">FB-5021</p>
        <div class="text-content">
            Propiedades: disponible en colores azul, rojo y blanco.
            Presentación: Individual.
        </div>
        <div class="variaciones-producto">
            <p>11</p>
            <p>22</p>
            <p>33</p>
        </div>
    </article>
    """

    from bs4 import BeautifulSoup

    card = BeautifulSoup(html, "lxml").select_one("article")
    result = CategoryProductExtractor().extract(card)

    assert result.color_stock == {}
    assert result.stock == 66


def test_product_extractor_does_not_guess_colores_disponibles_stock():
    html = """
    <html>
        <h1>Mochilas de Lona</h1>
        <p class="brxe-heading">FB-6002</p>
        <div>
            Colores disponibles: Azul, Rojo, Negro, Gris
        </div>
        <div>Stock Disponible 528 124 1686 355</div>
    </html>
    """

    from bs4 import BeautifulSoup

    product = ProductExtractor().extract(
        BeautifulSoup(html, "lxml"),
        url="https://example.com/producto/fb-6002/",
        category="Bolsas / Mochilas",
    )

    assert product.color_stock == {
        "Azul": 0,
        "Rojo": 0,
        "Negro": 0,
        "Gris": 0,
    }
    assert product.stock == 2693



def test_product_extractor_keeps_total_stock_when_color_names_have_no_per_color_stock():
    html = """
    <html>
        <h1>Lonchera de Neoprene</h1>
        <p class="brxe-heading">FB-6005</p>
        <div>
            Colores: Azul, Rojo, Negro
            Stock Disponible 330
        </div>
    </html>
    """

    from bs4 import BeautifulSoup

    product = ProductExtractor().extract(
        BeautifulSoup(html, "lxml"),
        url="https://example.com/producto/fb-6005/",
        category="Bolsas / Mochilas",
    )

    assert product.color_stock == {
        "Azul": 0,
        "Negro": 0,
        "Rojo": 0,
    }
    assert product.stock == 330


def test_product_extractor_does_not_guess_numeric_prefix_color_stock():
    html = """
    <html>
        <h1>Resaltador Flor</h1>
        <p class="brxe-heading">FB-1309</p>
        <div>
            5 colores: Fucsia, Naranja, Amarillo, Verde y Celeste
            Stock Disponible 10 20 30 40 50
        </div>
    </html>
    """

    from bs4 import BeautifulSoup

    product = ProductExtractor().extract(
        BeautifulSoup(html, "lxml"),
        url="https://example.com/producto/fb-1309/",
        category="Resaltadores Publicitarios",
    )

    assert product.color_stock == {
        "Fucsia": 0,
        "Naranja": 0,
        "Amarillo": 0,
        "Verde": 0,
        "Celeste": 0,
    }
    assert product.stock == 150


def test_product_extractor_reads_single_explicit_color():
    html = """
    <html>
        <h1>Estuche de Corcho</h1>
        <p class="brxe-heading">FB-1601</p>
        <div>
            Color: Negro
            Stock Disponible 0
        </div>
    </html>
    """

    from bs4 import BeautifulSoup

    product = ProductExtractor().extract(
        BeautifulSoup(html, "lxml"),
        url="https://example.com/producto/fb-1601/",
        category="Estuches",
    )

    assert product.color_stock == {"Negro": 0}
    assert product.stock == 0


def test_product_extractor_does_not_guess_descriptive_color_stock():
    html = """
    <html>
        <h1>Mochila Plegable Multifunción 3 en 1</h1>
        <p class="brxe-heading">FB-6001</p>
        <div>
            Esta mochila está disponible en colores modernos como
            azul, rojo, negro y gris.
            Stock Disponible 2 3415 0 1978
        </div>
    </html>
    """

    from bs4 import BeautifulSoup

    product = ProductExtractor().extract(
        BeautifulSoup(html, "lxml"),
        url="https://example.com/producto/fb-6001/",
        category="Bolsas / Mochilas",
    )

    assert product.color_stock == {
        "azul": 0,
        "rojo": 0,
        "negro": 0,
        "gris": 0,
    }
    assert product.stock == 5395


def test_category_extractor_does_not_guess_descriptive_color_stock():
    html = """
    <article>
        <h2 class="brxe-f6001">Mochila Plegable Multifunción 3 en 1</h2>
        <p class="brxe-a26f34">FB-6001</p>
        <div class="text-content">
            Esta mochila está disponible en colores modernos como
            azul, rojo, negro y gris.
            Presentación: Individual.
        </div>
        <div class="variaciones-producto">
            <p>2</p>
            <p>3415</p>
            <p>0</p>
            <p>1978</p>
        </div>
    </article>
    """

    from bs4 import BeautifulSoup

    card = BeautifulSoup(html, "lxml").select_one("article")
    result = CategoryProductExtractor().extract(card)

    assert result.color_stock == {
        "azul": 2,
        "negro": 3415,
        "rojo": 0,
        "gris": 1978,
    }
    assert result.stock == 5395


def test_category_extractor_does_not_guess_single_explicit_color_stock():
    html = """
    <article>
        <h2 class="brxe-f6002">Estuche de Corcho</h2>
        <p class="brxe-a26f34">FB-1601</p>
        <div class="text-content">
            Color: Negro
            Presentación: Individual.
        </div>
        <div class="variaciones-producto">
            <p>0</p>
        </div>
    </article>
    """

    from bs4 import BeautifulSoup

    card = BeautifulSoup(html, "lxml").select_one("article")
    result = CategoryProductExtractor().extract(card)

    assert result.color_stock == {}
    assert result.stock == 0




def test_collection_scraper_maps_fb6005_category_stock_to_correct_colors():
    class Fb6005CategoryScraper:
        def get_category_pages(self, url):
            return [url]

        def get_html(self, url):
            if "/producto/" in url:
                return """
                <html>
                    <h1>Lonchera de Neoprene</h1>
                    <p class="brxe-heading">FB-6005</p>
                    <div>Colores disponibles: Negro, Azul, Rojo</div>
                </html>
                """
            return """
            <html>
                <article class="jsfb-filterable">
                    <a href="/producto/lonchera-de-neoprene/">
                        <h2 class="brxe-f31760">Lonchera de Neoprene</h2>
                    </a>
                    <p class="brxe-a26f34">FB-6005</p>
                    <div class="text-content">
                        Colores disponibles: Azul, Rojo, Negro
                    </div>
                    <div class="ctn-variation">
                        <div class="variaciones-producto tooltip-ui" title="Rojo" sku="FB-6005-R">
                            <p>1022</p>
                        </div>
                        <div class="variaciones-producto tooltip-ui" title="Negro" sku="FB-6005-N">
                            <p>4</p>
                        </div>
                        <div class="variaciones-producto tooltip-ui" title="Azul" sku="FB-6005-A">
                            <p>330</p>
                        </div>
                    </div>
                </article>
            </html>
            """

    scraper = ProductCollectionScraper(
        Fb6005CategoryScraper(),
        card_extractor=lambda soup: [soup.select_one("article")],
        product_extractor=CategoryProductExtractor(),
        detail_extractor=ProductExtractor(),
    )

    products = scraper.scrape_category(
        Category(
            name="Bolsas / Mochilas",
            url="https://example.com/categoria/",
        ),
    )

    assert len(products) == 1
    assert products[0].color_stock == {
        "Rojo": 1022,
        "Negro": 4,
        "Azul": 330,
    }
    assert products[0].stock == 1356


def test_collection_scraper_uses_detail_color_names_for_multiple_card_stocks():
    class DetailNamesCategoryScraper:
        def get_category_pages(self, url):
            return [url]

        def get_html(self, url):
            if "/producto/" in url:
                return """
                <html>
                    <h1>Mochila Plegable Multifunción 3 en 1</h1>
                    <p class="brxe-heading">FB-6001</p>
                    <div>
                        Esta mochila está disponible en colores modernos como
                        azul, rojo, negro y gris.
                    </div>
                </html>
                """
            return """
            <html>
                <article class="jsfb-filterable">
                    <a href="/producto/mochila-plegable-multifuncion-3-en-1/">
                        <h2 class="brxe-f31760">
                            Mochila Plegable Multifunción 3 en 1
                        </h2>
                    </a>
                    <p class="brxe-a26f34">FB-6001</p>
                    <div class="variaciones-producto">
                        <p>2</p>
                        <p>3415</p>
                        <p>0</p>
                        <p>1978</p>
                    </div>
                </article>
            </html>
            """

    scraper = ProductCollectionScraper(
        DetailNamesCategoryScraper(),
        card_extractor=lambda soup: [soup.select_one("article")],
        product_extractor=CategoryProductExtractor(),
        detail_extractor=ProductExtractor(),
    )

    products = scraper.scrape_category(
        Category(
            name="Bolsas / Mochilas",
            url="https://example.com/categoria/",
        ),
    )

    assert len(products) == 1
    assert products[0].color_stock == {}
    assert products[0].stock == 5395



def test_collection_scraper_does_not_replace_total_stock_with_detail_color_names():
    class FakeTotalStockCategoryScraper:
        def get_category_pages(self, url):
            return [url]

        def get_html(self, url):
            if "/producto/" in url:
                return """
                <html>
                    <h1>Resaltador en Pote</h1>
                    <p class="brxe-heading">FB-1308</p>
                    <div>
                        Colores: Fucsia, Naranja, Amarillo, Verde y Celeste
                    </div>
                </html>
                """
            return """
            <html>
                <article>
                    <a href="/producto/resaltador-en-pote/">
                        <h2 class="brxe-f31760">Resaltador en Pote</h2>
                    </a>
                    <p class="brxe-a26f34">FB-1308</p>
                    <div class="text-content">
                        Resaltadores en 5 colores: Fucsia, Naranja, Amarillo,
                        Verde y Celeste.
                    </div>
                    <div class="variaciones-producto">
                        <p>5364</p>
                    </div>
                </article>
                </html>
                """

    scraper = ProductCollectionScraper(
        FakeTotalStockCategoryScraper(),
        card_extractor=lambda soup: [soup.select_one("article")],
        product_extractor=CategoryProductExtractor(),
        detail_extractor=ProductExtractor(),
    )

    products = scraper.scrape_category(
        Category(
            name="Resaltadores",
            url="https://example.com/categoria/",
        ),
    )

    assert products[0].color_stock == {}
    assert products[0].stock == 5364
