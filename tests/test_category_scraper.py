from scrapers.category_scraper import CategoryScraper


def test_category_scraper_extracts_categories():

    class FakeBrowser:
        def get(self, url):
            return "<html></html>"

    class FakeParser:
        def extract_categories(self, html):
            return [
                "Herramientas",
                "Electricidad"
            ]

    scraper = CategoryScraper(
        FakeBrowser(),
        FakeParser()
    )

    result = scraper.scrape("https://example.com/categories")

    assert result == [
        "Herramientas",
        "Electricidad"
    ]