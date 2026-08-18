from scrapers.collectors.category_scraper import CategoryScraper


def test_category_scraper_extracts_categories():

    class FakeBrowser:
        def get(self, url):
            return "<html></html>"

    class FakeParser:
        def extract_categories(self, html):
            return ["Herramientas", "Electricidad"]

    scraper = CategoryScraper(FakeBrowser(), FakeParser())

    result = scraper.scrape("https://example.com/categories")

    assert result == ["Herramientas", "Electricidad"]


def test_category_scraper_detects_embedded_jetsmartfilters_pages():
    html = """
    <html>
      <body>
        <div class="jet-filters-pagination__item" data-value="1">
          <div class="jet-filters-pagination__link">1</div>
        </div>
        <div class="jet-filters-pagination__item" data-value="2">
          <div class="jet-filters-pagination__link">2</div>
        </div>
        <div class="jet-filters-pagination__item" data-value="3">
          <div class="jet-filters-pagination__link">3</div>
        </div>
      </body>
    </html>
    """

    class FakeBrowser:
        def get(self, url):
            return html

    scraper = CategoryScraper(FakeBrowser())
    category_url = "https://example.com/categoria-producto/jarros-mug/"

    pages = scraper.get_category_pages(category_url)

    assert pages == [
        category_url,
        "https://example.com/categoria-producto/jarros-mug/page/2/",
        "https://example.com/categoria-producto/jarros-mug/page/3/",
    ]
