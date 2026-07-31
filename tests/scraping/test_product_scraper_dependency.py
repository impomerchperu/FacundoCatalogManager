from scrapers.product_scraper import ProductScraper


class FakeBrowser:
    def fetch(self, url):
        return """
        <html>
            <title>Producto Demo</title>
        </html>
        """


def test_product_scraper_with_dependency_injection():

    scraper = ProductScraper(FakeBrowser())

    result = scraper.scrape("https://demo.com")

    assert result.title.text == "Producto Demo"
