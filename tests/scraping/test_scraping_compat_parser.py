from scrapers.collectors.category_scraper import CategoryScraper


def test_category_scraper_uses_lxml_parser_without_custom_parser():
    scraper = CategoryScraper(browser="https://example.test")

    soup = scraper._parse("<div><a href='/producto/fb-001/'>FB-001</a></div>")

    assert soup.builder.NAME == "lxml"
