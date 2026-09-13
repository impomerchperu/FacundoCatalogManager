from models.scraping.category import Category
from scrapers.collectors.catalog_scraper import CatalogScraper


class FakeCategoryScraper:
    def __init__(self):
        self.calls = []

    def get_category_pages(self, url, expected_count=0):
        self.calls.append((url, expected_count))
        return [url]

    def scrape(self, url):
        return [Category("Papelería Grafipapel", "https://example.test/cat/", 79)]

    def _category_id(self, html):
        return 123

    def get_html(self, url):
        return '<body class="term-123"></body>'

    @staticmethod
    def _jsf_page_url(category_url, page):
        return f"{category_url.rstrip('/')}?product-page={page}"

    @staticmethod
    def _fetch_category_page_html(category_url, category_id, page, page_url):
        return f"<div class='product'>FB-{page:03d}</div>"

    def _cache_category_html(self, url, html):
        return None


def test_required_pages_uses_published_category_count():
    assert CatalogScraper._required_pages(25) == 1
    assert CatalogScraper._required_pages(26) == 2
    assert CatalogScraper._required_pages(50) == 2
    assert CatalogScraper._required_pages(79) == 4


def test_catalog_scraper_recovers_pages_missing_from_jsf_metadata():
    scraper = FakeCategoryScraper()
    catalog = CatalogScraper(scraper)

    pages = catalog._get_category_pages(
        Category("Papelería Grafipapel", "https://example.test/cat/", 79)
    )

    assert pages == [
        "https://example.test/cat/",
        "https://example.test/cat?product-page=2",
        "https://example.test/cat?product-page=3",
        "https://example.test/cat?product-page=4",
    ]
    assert scraper.calls == [("https://example.test/cat/", 79)]
