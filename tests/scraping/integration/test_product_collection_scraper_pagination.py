from types import SimpleNamespace

from models.scraping.category import Category
from scrapers.collectors.product_collection_scraper import ProductCollectionScraper


class FakeCategoryScraper:
    def __init__(self, pages):
        self.pages = pages
        self.get_html_calls = []

    def get_category_pages(self, category_url, expected_count=0):
        self.expected_count = expected_count
        return list(self.pages)

    def get_html(self, page_url):
        self.get_html_calls.append(page_url)
        return {
            self.pages[0]: (
                "<article class='product'>P001</article>"
                "<article class='product'>P002</article>"
            ),
            self.pages[1]: "<article class='product'>P003</article>",
            self.pages[2]: (
                "<article class='product'>P002</article>"
                "<article class='product'>P004</article>"
            ),
        }[page_url]


class FakeCardExtractor:
    def __call__(self, soup):
        return soup.select("article.product")


class FakeProductExtractor:
    def __call__(self, card, *, url, category):
        code = card.get_text(strip=True)
        return SimpleNamespace(
            code=code,
            name=f"Producto {code}",
            category=category,
            url=url,
        )


def test_collect_category_processes_every_discovered_page_and_deduplicates_products():
    category_url = "https://example.com/categoria/catalogo/"
    pages = [
        category_url,
        f"{category_url.rstrip('/')}?product-page=2",
        f"{category_url.rstrip('/')}?product-page=3",
    ]
    category_scraper = FakeCategoryScraper(pages)
    scraper = ProductCollectionScraper(
        category_scraper=category_scraper,
        card_extractor=FakeCardExtractor(),
        product_extractor=FakeProductExtractor(),
        max_workers=1,
    )

    products = scraper.collect_category(
        Category(name="Catalogo", url=category_url, expected_count=75)
    )

    assert category_scraper.expected_count == 75
    assert category_scraper.get_html_calls == pages
    assert [product[2].code for product in products] == [
        "P001",
        "P002",
        "P003",
        "P004",
    ]

    metrics = scraper.get_page_metrics()[category_url]
    assert metrics["pages_requested"] == 3
    assert metrics["pages_loaded"] == 3
    assert metrics["cards_found"] == 5
    assert metrics["unique_products"] == 4
    assert [page["unique_products"] for page in metrics["pages"]] == [2, 1, 1]
