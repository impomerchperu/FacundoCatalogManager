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


def test_collection_scraper_enriches_color_stock_from_detail():
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
    assert products[0].color_stock == {
        "Dorado": 6646,
        "Plateado": 7942,
    }
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
    assert products[0].color_stock == {
        "Amarillo": 1520,
        "Azul": 0,
        "Blanco": 20,
    }
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

    assert result.color_stock == {
        "Rojo": 100,
        "Negro": 200,
        "Azul": 300,
        "Gris Gun": 400,
        "Silver": 500,
    }
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

    assert result.color_stock == {
        "Fucsia": 10,
        "amarillo": 20,
        "verde": 30,
        "celeste": 40,
    }
    assert result.stock == 100


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
