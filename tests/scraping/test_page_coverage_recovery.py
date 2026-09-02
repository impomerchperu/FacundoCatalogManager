from threading import RLock

from scrapers.collectors import page_coverage_recovery_patch
from scrapers.collectors.category_scraper import CategoryScraper


def _new_scraper() -> CategoryScraper:
    scraper = object.__new__(CategoryScraper)
    scraper._category_html_cache = {}
    scraper._category_html_cache_lock = RLock()
    return scraper


def test_recovery_materializes_missing_expected_jsf_pages():
    scraper = _new_scraper()
    category_url = (
        "https://stock.importacionesfacundo.com/categoria-producto/"
        "papeles-fotograficos/"
    )
    category_html = """
    <html><body>
      <span class="sku">FB-7008</span>
      <div class="jet-filters-pagination">
        <div class="jet-filters-pagination__item" data-value="1"></div>
        <div class="jet-filters-pagination__item" data-value="2"></div>
        <div class="jet-filters-pagination__item" data-value="3"></div>
        <div class="jet-filters-pagination__item" data-value="4"></div>
      </div>
    </body></html>
    """
    responses = {
        2: "<div><span class='sku'>FB-7026</span></div>",
        3: "<div><span class='sku'>FB-7051</span></div>",
        4: "<div><span class='sku'>FB-7076</span></div>",
    }
    calls = []

    scraper._is_facundo_url = lambda _url: True
    scraper._category_id = lambda _html: 123
    scraper._jsf_page_url = CategoryScraper._jsf_page_url.__func__ if hasattr(CategoryScraper._jsf_page_url, "__func__") else CategoryScraper._jsf_page_url
    scraper._cache_category_html = lambda url, html: scraper._category_html_cache.__setitem__(url, html)
    scraper._fetch_jsf_page = lambda _url, _category_id, page: (
        calls.append(page) or (100, 4, responses.get(page, ""))
    )
    scraper._category_html_cache[category_url] = category_html

    pages = page_coverage_recovery_patch._recover_missing_pages(
        scraper,
        category_url,
        82,
        [category_url],
    )

    assert calls == [2, 3, 4]
    assert pages == [
        category_url,
        f"{category_url.rstrip('/')}?product-page=2",
        f"{category_url.rstrip('/')}?product-page=3",
        f"{category_url.rstrip('/')}?product-page=4",
    ]
