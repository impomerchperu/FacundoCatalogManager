import requests

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


def test_category_scraper_skips_invalid_embedded_page_without_aborting_category():
    category_url = "https://example.com/categoria-producto/jarros-mug/"
    category_html = """
    <div class="jet-filters-pagination__item" data-value="2">
      <div class="jet-filters-pagination__link">2</div>
    </div>
    <div class="jet-filters-pagination__item" data-value="3">
      <div class="jet-filters-pagination__link">3</div>
    </div>
    """
    page_3_url = f"{category_url}page/3/"
    page_3_html = "<div class=\"product-page\">productos pagina 3</div>"

    class FakeBrowser:
        def get(self, url):
            if url == category_url:
                return category_html
            if url == f"{category_url}page/2/":
                raise requests.HTTPError("404 Not Found")
            if url == page_3_url:
                return page_3_html
            raise AssertionError(f"URL inesperada: {url}")

    scraper = CategoryScraper(FakeBrowser())

    pages = scraper.get_category_pages(category_url)

    assert pages == [category_url, f"{category_url}page/2/", page_3_url]
