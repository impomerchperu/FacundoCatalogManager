import requests

from scrapers.collectors import page_coverage_recovery_patch as patch


def test_category_page_timeout_is_contained(monkeypatch):
    class FakeCategoryScraper:
        def _is_facundo_url(self, url):
            return False

    def raise_timeout(*args, **kwargs):
        raise requests.exceptions.ReadTimeout("timed out")

    monkeypatch.setattr(patch, "_ORIGINAL_GET_CATEGORY_PAGES", raise_timeout)

    pages = patch._get_category_pages_with_recovery(
        FakeCategoryScraper(),
        "https://stock.importacionesfacundo.com/categoria-producto/test/",
        expected_count=50,
    )

    assert pages == []


def test_category_html_timeout_returns_empty_html(monkeypatch):
    class FakeCategoryScraper:
        pass

    def raise_timeout(*args, **kwargs):
        raise requests.exceptions.ReadTimeout("timed out")

    monkeypatch.setattr(patch, "_ORIGINAL_GET_HTML", raise_timeout)

    html = patch._get_html_with_recovery(
        FakeCategoryScraper(),
        "https://stock.importacionesfacundo.com/categoria-producto/test/",
    )

    assert html == ""


def test_jsf_recovery_timeout_does_not_abort_remaining_pages(monkeypatch):
    class FakeCategoryScraper:
        def _is_facundo_url(self, url):
            return True

        def _category_id(self, html):
            return 123

        def _cache_category_html(self, url, html):
            self.cached = (url, html)

        def _jsf_page_url(self, category_url, page):
            return f"{category_url}?product-page={page}"

    scraper = FakeCategoryScraper()

    monkeypatch.setattr(patch, "_cached_category_html", lambda *_: "<html></html>")
    monkeypatch.setattr(patch.CategoryScraper, "_pagination_max_page", staticmethod(lambda _: 3))
    monkeypatch.setattr(
        patch,
        "_ORIGINAL_RESILIENT_GET_CATEGORY_PAGES",
        lambda *args, **kwargs: ["https://stock.importacionesfacundo.com/categoria-producto/test/"],
    )

    def raise_timeout(*args, **kwargs):
        raise requests.exceptions.ReadTimeout("timed out")

    monkeypatch.setattr(scraper, "_fetch_jsf_page", raise_timeout, raising=False)

    pages = patch._get_resilient_category_pages_with_recovery(
        scraper,
        "https://stock.importacionesfacundo.com/categoria-producto/test/",
        expected_count=75,
    )

    assert len(pages) == 1
