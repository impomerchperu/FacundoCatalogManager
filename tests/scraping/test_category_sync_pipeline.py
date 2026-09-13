from types import SimpleNamespace

from models.scraping.category import Category
from scrapers.collectors.product_collection_scraper import ProductCollectionScraper


class FakeCategoryScraper:
    def __init__(self):
        self.calls = []
        self.html = {
            "https://stock.importacionesfacundo.com/categoria-producto/demo/": (
                '<div class="card"><a href="/producto/uno/"><h3>UNO</h3></a></div>'
            ),
            "https://stock.importacionesfacundo.com/categoria-producto/demo?product-page=2": (
                '<div class="card"><a href="/producto/dos/"><h3>DOS</h3></a></div>'
            ),
        }

    def get_category_pages(self, category_url, expected_count=0):
        self.calls.append((category_url, expected_count))
        return [
            category_url,
            f"{category_url.rstrip('/')}?product-page=2",
        ]

    def get_html(self, url):
        return self.html[url]

    @staticmethod
    def _parse(html):
        from bs4 import BeautifulSoup

        return BeautifulSoup(html, "html.parser")


class FakeCardExtractor:
    def extract(self, soup):
        return soup.select(".card")


class FakeProductExtractor:
    def extract(self, card, *, url, category):
        code = card.select_one("h3").get_text(strip=True)
        return SimpleNamespace(
            code=code,
            name=code,
            category=category,
            description="",
            image_url="",
            url=url,
        )


def test_collection_scraper_passes_category_expected_count_to_pagination():
    category_scraper = FakeCategoryScraper()
    scraper = ProductCollectionScraper(
        category_scraper=category_scraper,
        card_extractor=FakeCardExtractor(),
        product_extractor=FakeProductExtractor(),
    )

    category = Category(
        name="Demo",
        url="https://stock.importacionesfacundo.com/categoria-producto/demo/",
        expected_count=50,
    )

    products = scraper.collect_category(category)

    assert category_scraper.calls == [(category.url, 50)]
    assert [product.code for _, _, product in products] == ["UNO", "DOS"]
    metrics = scraper.get_page_metrics()[category.url]
    assert metrics["pages_expected"] == 2
    assert metrics["pages_requested"] == 2
    assert metrics["pages_loaded"] == 2
    assert metrics["cards_found"] == 2
