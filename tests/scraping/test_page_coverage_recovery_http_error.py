from __future__ import annotations

from threading import RLock

import requests

from scrapers.collectors import page_coverage_recovery_patch
from scrapers.collectors.category_scraper import CategoryScraper

CATEGORY_URL = "https://stock.importacionesfacundo.com/categoria-producto/papeles-fotograficos/"
CATEGORY_HTML = """
<html><body>
  <span class="sku">FB-7008</span>
  <div class="jet-filters-pagination">
    <div class="jet-filters-pagination__item" data-value="1"></div>
    <div class="jet-filters-pagination__item" data-value="2"></div>
  </div>
</body></html>
"""


class FailingBoundaryFetcher:
    def __init__(self) -> None:
        self.calls = 0

    def __call__(self, _url: str, _category_id: int, _page: int):
        self.calls += 1
        response = requests.Response()
        response.status_code = 500
        response.url = "https://stock.importacionesfacundo.com/wp-admin/admin-ajax.php"
        raise requests.HTTPError(response=response)


def test_recovery_keeps_valid_pages_when_boundary_http_error_occurs():
    scraper = object.__new__(CategoryScraper)
    scraper._category_html_cache = {CATEGORY_URL: CATEGORY_HTML}
    scraper._category_html_cache_lock = RLock()
    fetcher = FailingBoundaryFetcher()
    cached = []

    scraper._is_facundo_url = lambda _url: True
    scraper._category_id = lambda _html: 123
    scraper._fetch_jsf_page = fetcher
    scraper._jsf_page_url = lambda url, page: f"{url}?product-page={page}"
    scraper._cache_category_html = lambda url, html: cached.append((url, html))

    pages = page_coverage_recovery_patch._recover_missing_pages(
        scraper,
        CATEGORY_URL,
        26,
        [CATEGORY_URL],
    )

    assert pages == [CATEGORY_URL]
    assert fetcher.calls == 1
    assert cached == []
