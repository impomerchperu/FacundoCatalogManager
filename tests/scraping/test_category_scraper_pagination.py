from scrapers.collectors.category_scraper import CategoryScraper


class FakeBrowser:
    def get(self, url):
        return "<div>Producto(s) 61</div>"


def test_category_scraper_generates_pages_from_published_product_count():
    scraper = CategoryScraper(FakeBrowser())

    pages = scraper.get_category_pages(
        "https://example.com/categoria/",
    )

    assert pages == [
        "https://example.com/categoria/",
        "https://example.com/categoria/page/2/",
        "https://example.com/categoria/page/3/",
    ]
