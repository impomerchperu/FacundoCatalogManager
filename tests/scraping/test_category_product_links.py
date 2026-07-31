from scrapers.category_scraper import CategoryScraper
from scrapers.parser import Parser
from scrapers.product_link_extractor import ProductLinkExtractor


class FakeBrowser:

    def get(self, url):

        return """
        <html>

            <a href="/producto-a">
                Producto A
            </a>

            <a href="/producto-b">
                Producto B
            </a>

        </html>
        """


def test_category_scraper_get_product_urls():

    scraper = CategoryScraper(
        FakeBrowser(),
        Parser(),
        ProductLinkExtractor()
    )


    urls = scraper.get_product_urls(
        "https://example.com/categoria"
    )


    assert len(urls) == 2

    assert "/producto-a" in urls

    assert "/producto-b" in urls