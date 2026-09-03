from models.scraping.category import Category
from scrapers.collectors.product_collection_scraper import ProductCollectionScraper
from scrapers.extractors.category_product_extractor import CategoryProductExtractor
from scrapers.extractors.product_extractor import ProductExtractor


def _run_missing_price_case(price_html: str):
    class CategoryScraper:
        def get_category_pages(self, url):
            return [url]

        def get_html(self, url):
            return f"""
            <html>
                <article>
                    <a href="/producto/producto-precios/">
                        <img src="https://example.com/producto.jpg">
                        <h2 class="brxe-f31760">Producto precios</h2>
                    </a>
                    <p class="brxe-a26f34">FB-1237</p>
                    <div class="text-content">Producto con precios parciales.</div>
                    <div class="variaciones-producto"><p>10</p></div>
                    {price_html}
                </article>
            </html>
            """

    scraper = ProductCollectionScraper(
        CategoryScraper(),
        card_extractor=lambda soup: [soup.select_one("article")],
        product_extractor=CategoryProductExtractor(),
        detail_extractor=ProductExtractor(),
    )
    scraper.scrape_category(
        Category(name="Promocionales", url="https://example.com/promocionales/")
    )
    return scraper.get_detail_metrics()


def test_detail_reason_metrics_identify_parser_missed_sample_price():
    metrics = _run_missing_price_case(
        "<h3>Precio Muestra</h3>"
        "<h4>Disponible bajo consulta</h4>"
        "<h3>Precio Ciento</h3><h4>S/ 700.00</h4>"
        "<h3>Precio Millar</h3><h4>S/ 6500.00</h4>"
    )

    assert metrics["detail_requests"] == 1
    assert metrics["detail_reason_counts"] == {
        "requested_missing_prices": 1,
        "requested_missing_sample": 1,
    }


def test_missing_price_is_requested_even_without_price_label_on_card():
    metrics = _run_missing_price_case(
        "<h3>Precio Ciento</h3><h4>S/ 700.00</h4>"
        "<h3>Precio Por Caja</h3><h4>S/ 650.00</h4>"
    )

    assert metrics["detail_requests"] == 1
    assert metrics["detail_reason_counts"] == {
        "requested_missing_prices": 1,
        "requested_missing_sample": 1,
        "requested_missing_hundred": 1,
        "requested_missing_thousand": 1,
    }


def test_missing_hundred_is_requested_only_when_label_is_advertised():
    metrics = _run_missing_price_case(
        "<h3>Precio Muestra</h3><h4>S/ 8.00</h4>"
        "<h3>Precio Ciento</h3><h4>Consultar</h4>"
        "<h3>Precio Millar</h3><h4>S/ 6500.00</h4>"
    )

    assert metrics["detail_requests"] == 1
    assert metrics["detail_reason_counts"] == {
        "requested_missing_prices": 1,
        "requested_missing_hundred": 1,
    }


def test_missing_multiple_advertised_prices_are_all_recorded():
    metrics = _run_missing_price_case(
        "<h3>Precio Muestra</h3><h4>Consultar</h4>"
        "<h3>Precio Ciento</h3><h4>S/ 700.00</h4>"
        "<h3>Precio Millar</h3><h4>Consultar</h4>"
    )

    assert metrics["detail_requests"] == 1
    assert metrics["detail_reason_counts"] == {
        "requested_missing_prices": 1,
        "requested_missing_sample": 1,
        "requested_missing_thousand": 1,
    }
