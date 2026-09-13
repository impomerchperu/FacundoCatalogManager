from types import SimpleNamespace

from models.scraping.category import Category
from scrapers.collectors.product_collection_scraper import ProductCollectionScraper


class FakeCategoryScraper:
    def __init__(self, pages):
        self.pages = pages

    def get_category_pages(self, url, expected_count=0):
        assert expected_count == 82
        return list(self.pages)

    def get_html(self, url):
        return self.pages[url]

    @staticmethod
    def _parse(html):
        from bs4 import BeautifulSoup

        return BeautifulSoup(html, "html.parser")


class FakeCardExtractor:
    def extract(self, soup):
        return soup.select("article.product")


class FakeProductExtractor:
    def extract(self, card, *, url, category):
        return SimpleNamespace(
            code=card.get("data-code", ""),
            name=card.get_text(" ", strip=True),
            category=category,
            url=url,
        )


def _page(codes):
    cards = "".join(
        f'<article class="product" data-code="{code}">{code}</article>'
        for code in codes
    )
    return f"<main>{cards}</main>"


def test_collect_category_records_every_expected_page_and_card_count():
    category_url = "https://stock.importacionesfacundo.com/categoria-producto/test/"
    page_urls = [
        category_url,
        f"{category_url}?product-page=2",
        f"{category_url}?product-page=3",
        f"{category_url}?product-page=4",
    ]
    codes = [f"P{i:03d}" for i in range(1, 83)]
    pages = {
        page_urls[0]: _page(codes[:25]),
        page_urls[1]: _page(codes[25:50]),
        page_urls[2]: _page(codes[50:75]),
        page_urls[3]: _page(codes[75:]),
    }
    scraper = ProductCollectionScraper(
        FakeCategoryScraper(pages),
        FakeCardExtractor(),
        FakeProductExtractor(),
    )

    products = scraper.collect_category(
        Category("Test", category_url, expected_count=82)
    )

    metrics = scraper.get_page_metrics()[category_url]
    assert len(products) == 82
    assert metrics["expected_count"] == 82
    assert metrics["pages_expected"] == 4
    assert metrics["pages_requested"] == 4
    assert metrics["pages_loaded"] == 4
    assert metrics["cards_found"] == 82
    assert metrics["unique_products"] == 82
    assert [page["cards"] for page in metrics["pages"]] == [25, 25, 25, 7]


def test_collect_category_metrics_expose_missing_page_html():
    category_url = "https://stock.importacionesfacundo.com/categoria-producto/test/"
    page_urls = [
        category_url,
        f"{category_url}?product-page=2",
        f"{category_url}?product-page=3",
        f"{category_url}?product-page=4",
    ]
    pages = {
        page_urls[0]: _page([f"P{i:03d}" for i in range(1, 26)]),
        page_urls[1]: "",
        page_urls[2]: _page([f"P{i:03d}" for i in range(51, 76)]),
        page_urls[3]: _page([f"P{i:03d}" for i in range(76, 83)]),
    }
    scraper = ProductCollectionScraper(
        FakeCategoryScraper(pages),
        FakeCardExtractor(),
        FakeProductExtractor(),
    )

    scraper.collect_category(Category("Test", category_url, expected_count=82))

    metrics = scraper.get_page_metrics()[category_url]
    assert metrics["pages_requested"] == 4
    assert metrics["pages_loaded"] == 3
    assert metrics["cards_found"] == 57
    assert metrics["pages"][1]["html_available"] is False
    assert metrics["pages"][1]["cards"] == 0
