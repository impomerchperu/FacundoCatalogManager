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
                <div>Colores | Dorado, Plateado</div>
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
