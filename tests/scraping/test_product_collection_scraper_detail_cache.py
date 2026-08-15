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

        return f"""
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
