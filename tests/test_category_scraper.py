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
    <html><body>
      <div class="jet-filters-pagination__item" data-value="1">
        <div class="jet-filters-pagination__link">1</div>
      </div>
      <div class="jet-filters-pagination__item" data-value="2">
        <div class="jet-filters-pagination__link">2</div>
      </div>
      <div class="jet-filters-pagination__item" data-value="3">
        <div class="jet-filters-pagination__link">3</div>
      </div>
    </body></html>
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
    page_3_html = '<div class="product-page">productos pagina 3</div>'

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


def test_category_scraper_uses_authoritative_expected_count_for_hidden_pages():
    category_url = "https://example.com/categoria-producto/catalogo/"
    first_page_codes = " ".join(f"FB-{number:03d}" for number in range(1, 26))
    second_page_codes = " ".join(f"FB-{number:03d}" for number in range(26, 51))
    first_page_html = f"<div>{first_page_codes}</div>"
    second_page_html = f"<div>{second_page_codes}</div>"

    class FakeBrowser:
        def get(self, url):
            if url == category_url:
                return first_page_html
            if url == f"{category_url}?product-page=2":
                return second_page_html
            raise requests.HTTPError("404 Not Found")

    scraper = CategoryScraper(FakeBrowser())
    pages = scraper.get_category_pages(category_url, expected_count=50)
    assert pages == [category_url, f"{category_url}?product-page=2"]


def test_category_scraper_stops_probing_when_expected_count_is_reached():
    category_url = "https://example.com/categoria-producto/catalogo/"
    pages_html = {
        category_url: " ".join(f"FB-{number:03d}" for number in range(1, 26)),
        f"{category_url}?product-page=2": " ".join(
            f"FB-{number:03d}" for number in range(26, 51)
        ),
    }
    requested = []

    class FakeBrowser:
        def get(self, url):
            requested.append(url)
            if url in pages_html:
                return f"<div>{pages_html[url]}</div>"
            raise requests.HTTPError("404 Not Found")

    scraper = CategoryScraper(FakeBrowser())
    pages = scraper.get_category_pages(category_url, expected_count=50)

    assert pages == [category_url, f"{category_url}?product-page=2"]
    assert all("page=3" not in url and "page/3" not in url for url in requested)
    assert all("paged=3" not in url and "page_num=3" not in url for url in requested)


def test_category_scraper_ignores_duplicate_variant_and_continues():
    category_url = "https://example.com/categoria-producto/catalogo/"
    first = " ".join(f"FB-{number:03d}" for number in range(1, 26))
    second = " ".join(f"FB-{number:03d}" for number in range(26, 51))
    third = " ".join(f"FB-{number:03d}" for number in range(51, 76))

    class FakeBrowser:
        def get(self, url):
            if url == category_url:
                return f"<div>{first}</div>"
            if url.endswith("?product-page=2") or url.endswith("/page/2/"):
                return f"<div>{first}</div>"
            if url.endswith("?paged=2"):
                return f"<div>{second}</div>"
            if url.endswith("?product-page=3"):
                return f"<div>{third}</div>"
            raise requests.HTTPError("404 Not Found")

    scraper = CategoryScraper(FakeBrowser())
    pages = scraper.get_category_pages(category_url, expected_count=75)

    assert len(pages) == 3
    assert pages[0] == category_url
    assert pages[1].endswith("?paged=2")
    assert pages[2].endswith("?product-page=3")
