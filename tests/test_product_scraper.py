from scrapers.product_scraper import ProductScraper


def test_product_scraper():

    scraper = ProductScraper()

    result = scraper.scrape("https://example.com")

    assert result is not None
    assert result.title is not None
