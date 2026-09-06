from types import SimpleNamespace

from bs4 import BeautifulSoup

from scrapers.collectors.product_collection_scraper import ProductCollectionScraper


class FakeCategoryScraper:
    def __init__(self):
        self.pages = [
            "https://example.test/categoria/",
            "https://example.test/categoria/?product-page=2",
        ]

    def get_category_pages(self, url, expected_count=0):
        assert url == "https://example.test/categoria/"
        assert expected_count == 3
        return self.pages

    def get_html(self, url):
        if url.endswith("/?product-page=2"):
            return """
            <div class="product"><p>FB-002</p></div>
            <div class="product"><p>FB-003</p></div>
            """
        return """
        <div class="product"><p>FB-001</p></div>
        <div class="product"><p>FB-002</p></div>
        """


def test_product_collection_scraper_replaces_legacy_pagination_contract():
    category_scraper = FakeCategoryScraper()

    def extract_cards(soup):
        return soup.select(".product")

    def extract_product(card, *, url, category):
        code = card.find("p").get_text(strip=True)
        return SimpleNamespace(
            code=code,
            name=code,
            category=category,
            url=url,
        )

    scraper = ProductCollectionScraper(
        category_scraper=category_scraper,
        card_extractor=extract_cards,
        product_extractor=extract_product,
        detail_extractor=None,
        max_workers=1,
    )

    products = scraper.scrape_category(
        SimpleNamespace(
            url="https://example.test/categoria/",
            name="Categoría prueba",
            expected_count=3,
        )
    )

    assert [product.code for product in products] == [
        "FB-001",
        "FB-002",
        "FB-003",
    ]

    metrics = scraper.get_page_metrics()["https://example.test/categoria/"]
    assert metrics["pages_requested"] == 2
    assert metrics["pages_loaded"] == 2
    assert metrics["cards_found"] == 4
    assert metrics["unique_products"] == 3
