from threading import RLock

from scrapers.collectors import category_pagination_patch
from scrapers.collectors.category_scraper import CategoryScraper


def _new_scraper() -> CategoryScraper:
    scraper = object.__new__(CategoryScraper)
    scraper._category_html_cache = {}
    scraper._category_html_cache_lock = RLock()
    scraper._jsf_metadata_cache = {}
    scraper._jsf_page_cache = {}
    scraper._jsf_cache_lock = RLock()
    scraper.MAX_HIDDEN_PAGE_PROBES = 100
    return scraper


def _products(start: int, count: int) -> str:
    links = "".join(
        f'<a href="/producto/producto-{index:03d}/">Producto {index}</a>'
        for index in range(start, start + count)
    )
    return f"<html><body>{links}</body></html>"


def test_visible_jetsmartfilters_pagination_is_honored():
    scraper = _new_scraper()
    category_url = (
        "https://stock.importacionesfacundo.com/"
        "categoria-producto/papeles-fotograficos/"
    )
    visible_pagination = """
    <div class="brxe-jet-smart-filters-pagination">
      <div class="jet-filters-pagination">
        <div class="jet-filters-pagination__item" data-value="1"></div>
        <div class="jet-filters-pagination__item" data-value="2"></div>
        <div class="jet-filters-pagination__item" data-value="3"></div>
        <div class="jet-filters-pagination__item jet-filters-pagination__current" data-value="4">
          <div class="jet-filters-pagination__link">4</div>
        </div>
      </div>
    </div>
    """
    category_html = _products(1, 25) + visible_pagination
    pages = {
        1: (100, 1, _products(1, 25)),
        2: (100, 1, _products(26, 25)),
        3: (100, 1, _products(51, 25)),
        4: (100, 1, _products(76, 25)),
        5: (100, 1, ""),
    }
    calls = []

    scraper.get_html = lambda _url: category_html
    scraper._is_facundo_url = lambda _url: True
    scraper._category_id = lambda _html: 123

    def fetch(_url, _category_id, page):
        calls.append(page)
        return pages[page]

    scraper._fetch_jsf_page = fetch

    result = category_pagination_patch._get_category_pages(
        scraper,
        category_url,
        expected_count=0,
    )

    assert calls == [1, 2, 3, 4, 5]
    assert result == [
        category_url,
        f"{category_url}?product-page=2",
        f"{category_url}?product-page=3",
        f"{category_url}?product-page=4",
    ]
