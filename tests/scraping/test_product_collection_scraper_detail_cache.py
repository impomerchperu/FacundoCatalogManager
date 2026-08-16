from models.scraping.category import Category
from scrapers.collectors.product_collection_scraper import ProductCollectionScraper
from scrapers.extractors.category_product_extractor import CategoryProductExtractor
from scrapers.extractors.product_extractor import ProductExtractor


class SharedProductCategoryScraper:
    def __init__(self):
        self.detail_requests = []

    def get_category_pages(self, url):
        return [url]

    def get_html(self, url):
        if "/producto/" in url:
            self.detail_requests.append(url)
            return """
            <html>
                <h1>Producto compartido</h1>
                <p class="brxe-heading">FB-9999</p>
                <div>Colores: Rojo</div>
            </html>
            """

        return """
        <html>
            <article>
                <a href="/producto/producto-compartido/">
                    <h2 class="brxe-f31760">Producto compartido</h2>
                </a>
                <p class="brxe-a26f34">FB-9999</p>
                <div class="variaciones-producto"><p>10</p></div>
            </article>
        </html>
        """


def test_detail_cache_reuses_product_code_across_categories():
    category_scraper = SharedProductCategoryScraper()
    scraper = ProductCollectionScraper(
        category_scraper,
        card_extractor=lambda soup: [soup.select_one("article")],
        product_extractor=CategoryProductExtractor(),
        detail_extractor=ProductExtractor(),
    )

    first = scraper.scrape_category(
        Category(name="Jarros", url="https://example.com/jarros/")
    )
    second = scraper.scrape_category(
        Category(name="Promocionales", url="https://example.com/promocionales/")
    )

    assert len(first) == 1
    assert len(second) == 1
    assert len(category_scraper.detail_requests) == 1

    metrics = scraper.get_detail_metrics()
    assert metrics["detail_requests"] == 1
    assert metrics["detail_cache_hits"] == 1
    assert metrics["detail_cache_size"] == 1

    assert first[0].category == "Jarros"
    assert second[0].category == "Promocionales"


def test_detail_cache_is_cleared_between_full_runs():
    category_scraper = SharedProductCategoryScraper()
    scraper = ProductCollectionScraper(
        category_scraper,
        card_extractor=lambda soup: [soup.select_one("article")],
        product_extractor=CategoryProductExtractor(),
        detail_extractor=ProductExtractor(),
    )

    scraper.scrape_category(
        Category(name="Jarros", url="https://example.com/jarros/")
    )
    assert len(category_scraper.detail_requests) == 1

    scraper.reset_detail_metrics()
    scraper.scrape_category(
        Category(name="Jarros", url="https://example.com/jarros/")
    )

    assert len(category_scraper.detail_requests) == 2
    metrics = scraper.get_detail_metrics()
    assert metrics["detail_requests"] == 1
    assert metrics["detail_cache_hits"] == 0
    assert metrics["detail_cache_size"] == 1


def test_complete_card_color_stock_skips_detail_request():
    category_scraper = SharedProductCategoryScraper()
    scraper = ProductCollectionScraper(
        category_scraper,
        card_extractor=lambda soup: [soup.select_one("article")],
        product_extractor=CategoryProductExtractor(),
        detail_extractor=ProductExtractor(),
    )

    html = """
    <html>
        <article>
            <a href="/producto/producto-con-colores/">
                <h2 class="brxe-f31760">Producto con colores</h2>
            </a>
            <p class="brxe-a26f34">FB-1234</p>
            <div class="variaciones-producto">
                <span data-color="Rojo">Rojo</span>
                <span data-color="Azul">Azul</span>
                <p>Rojo: 10</p>
                <p>Azul: 20</p>
            </div>
        </article>
    </html>
    """

    category_scraper.get_html = lambda url: html
    result = scraper.scrape_category(
        Category(name="Promocionales", url="https://example.com/promocionales/")
    )

    assert len(result) == 1
    assert category_scraper.detail_requests == []
    assert result[0].url == "https://example.com/producto/producto-con-colores/"
    assert result[0].color_stock == {"Rojo": 10, "Azul": 20}
    assert result[0].stock == 30

    metrics = scraper.get_detail_metrics()
    assert metrics["detail_requests"] == 0
    assert metrics["detail_skipped"] == 1
    assert metrics["detail_reason_counts"] == {"skipped_complete_color_stock": 1}


def test_complete_single_stock_card_skips_detail_when_all_fields_are_present():
    category_scraper = SharedProductCategoryScraper()
    scraper = ProductCollectionScraper(
        category_scraper,
        card_extractor=lambda soup: [soup.select_one("article")],
        product_extractor=CategoryProductExtractor(),
        detail_extractor=ProductExtractor(),
    )

    html = """
    <html>
        <article>
            <a href="/producto/producto-completo/">
                <img src="https://example.com/producto.jpg">
                <h2 class="brxe-f31760">Producto completo</h2>
            </a>
            <p class="brxe-a26f34">FB-1235</p>
            <div class="text-content">Producto listo para catálogo.</div>
            <div class="variaciones-producto"><p>152</p></div>
            <h3>Precio Muestra</h3><h4>S/ 8.00</h4>
            <h3>Precio Ciento</h3><h4>S/ 700.00</h4>
            <h3>Precio Millar</h3><h4>S/ 6500.00</h4>
        </article>
    </html>
    """

    category_scraper.get_html = lambda url: html
    result = scraper.scrape_category(
        Category(name="Promocionales", url="https://example.com/promocionales/")
    )

    assert len(result) == 1
    assert category_scraper.detail_requests == []
    assert result[0].url == "https://example.com/producto/producto-completo/"
    assert result[0].stock == 152

    metrics = scraper.get_detail_metrics()
    assert metrics["detail_requests"] == 0
    assert metrics["detail_skipped"] == 1
    assert metrics["detail_reason_counts"] == {"skipped_complete_single_stock": 1}


def test_detail_reason_metrics_identify_missing_card_data():
    category_scraper = SharedProductCategoryScraper()
    scraper = ProductCollectionScraper(
        category_scraper,
        card_extractor=lambda soup: [soup.select_one("article")],
        product_extractor=CategoryProductExtractor(),
        detail_extractor=ProductExtractor(),
    )

    html = """
    <html>
        <article>
            <a href="/producto/producto-incompleto/">
                <h2 class="brxe-f31760">Producto incompleto</h2>
            </a>
            <p class="brxe-a26f34">FB-1236</p>
            <div class="variaciones-producto"><p>10</p></div>
        </article>
    </html>
    """

    category_scraper.get_html = lambda url: html
    scraper.scrape_category(
        Category(name="Promocionales", url="https://example.com/promocionales/")
    )

    metrics = scraper.get_detail_metrics()
    assert metrics["detail_requests"] == 1
    assert metrics["detail_reason_counts"] == {
        "requested_missing_fields": 1,
        "requested_missing_description": 1,
        "requested_missing_image_url": 1,
    }


def test_detail_reason_metrics_classify_labeled_multiple_stock():
    category_scraper = SharedProductCategoryScraper()
    scraper = ProductCollectionScraper(
        category_scraper,
        card_extractor=lambda soup: [soup.select_one("article")],
        product_extractor=CategoryProductExtractor(),
        detail_extractor=ProductExtractor(),
    )

    html = """
    <html>
        <article>
            <a href="/producto/producto-colores-incompleto/">
                <h2 class="brxe-f31760">Producto con colores</h2>
            </a>
            <p class="brxe-a26f34">FB-1237</p>
            <div class="variaciones-producto">
                <p>Rojo: 10</p>
                <p>Azul: 20</p>
            </div>
        </article>
    </html>
    """

    category_scraper.get_html = lambda url: html
    scraper.scrape_category(
        Category(name="Promocionales", url="https://example.com/promocionales/")
    )

    metrics = scraper.get_detail_metrics()
    assert metrics["detail_reason_counts"] == {
        "requested_multiple_labeled_stock": 1,
    }


def test_detail_reason_metrics_classify_multiple_numeric_stock():
    category_scraper = SharedProductCategoryScraper()
    scraper = ProductCollectionScraper(
        category_scraper,
        card_extractor=lambda soup: [soup.select_one("article")],
        product_extractor=CategoryProductExtractor(),
        detail_extractor=ProductExtractor(),
    )

    html = """
    <html>
        <article>
            <a href="/producto/producto-varios-stocks/">
                <h2 class="brxe-f31760">Producto con varios stocks</h2>
            </a>
            <p class="brxe-a26f34">FB-1238</p>
            <div class="variaciones-producto">
                <p>10</p>
                <p>20</p>
            </div>
        </article>
    </html>
    """

    category_scraper.get_html = lambda url: html
    scraper.scrape_category(
        Category(name="Promocionales", url="https://example.com/promocionales/")
    )

    metrics = scraper.get_detail_metrics()
    assert metrics["detail_reason_counts"] == {
        "requested_multiple_numeric_stock": 1,
    }


def test_detail_reason_metrics_classify_missing_stock():
    category_scraper = SharedProductCategoryScraper()
    scraper = ProductCollectionScraper(
        category_scraper,
        card_extractor=lambda soup: [soup.select_one("article")],
        product_extractor=CategoryProductExtractor(),
        detail_extractor=ProductExtractor(),
    )

    html = """
    <html>
        <article>
            <a href="/producto/producto-sin-stock/">
                <h2 class="brxe-f31760">Producto sin stock visible</h2>
            </a>
            <p class="brxe-a26f34">FB-1239</p>
        </article>
    </html>
    """

    category_scraper.get_html = lambda url: html
    scraper.scrape_category(
        Category(name="Promocionales", url="https://example.com/promocionales/")
    )

    metrics = scraper.get_detail_metrics()
    assert metrics["detail_reason_counts"] == {
        "requested_missing_stock": 1,
    }
