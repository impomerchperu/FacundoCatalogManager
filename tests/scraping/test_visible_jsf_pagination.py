import json
from threading import RLock

import pytest

from scrapers.collectors import category_pagination_engine
from scrapers.collectors.category_scraper import CategoryScraper


def _new_scraper() -> CategoryScraper:
    scraper = CategoryScraper(browser=object())
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
        1: _products(1, 25),
        2: _products(26, 25),
        3: _products(51, 25),
        4: _products(76, 25),
        5: "",
    }
    calls = []

    scraper.get_html = lambda _url: category_html
    scraper._is_facundo_url = lambda _url: True
    scraper._category_id = lambda _html: 123

    def post(_payload):
        page = next(
            int(value)
            for key, value in _payload
            if key in {"defaults[paged]", "props[page]", "paged"}
        )
        calls.append(page)
        return json.dumps(
            {
                "found_posts": 100,
                "max_num_pages": 1,
                "rendered_content": pages[page],
            }
        )

    scraper._post_jsf = post

    result = category_pagination_engine.get_category_pages(
        scraper,
        category_url,
        expected_count=0,
    )

    assert calls == [2, 3, 4, 5]
    assert result == [
        category_url,
        f"{category_url.rstrip('/')}?product-page=2",
        f"{category_url.rstrip('/')}?product-page=3",
        f"{category_url.rstrip('/')}?product-page=4",
    ]


@pytest.mark.parametrize(
    ("expected_count", "seen_count", "should_probe"),
    [
        (0, 0, True),
        (25, 25, False),
        (25, 24, True),
        (25, 26, True),
    ],
)
def test_boundary_probe_guard_requires_exact_expected_count(
    expected_count,
    seen_count,
    should_probe,
):
    seen = {
        f"https://example.test/product/{index}"
        for index in range(seen_count)
    }
    assert (
        category_pagination_engine._should_probe_boundary_page(
            expected_count,
            seen,
        )
        is should_probe
    )


def test_boundary_probe_is_skipped_when_expected_count_is_exact(monkeypatch):
    scraper = _new_scraper()
    category_url = (
        "https://stock.importacionesfacundo.com/"
        "categoria-producto/catalogo/"
    )
    category_html = _products(1, 25)

    monkeypatch.setattr(
        category_pagination_engine,
        "_initial_jsf_page",
        lambda *args, **kwargs: (25, 1, category_html),
    )

    def fail_probe(*args, **kwargs):
        raise AssertionError("boundary probe must be skipped")

    monkeypatch.setattr(
        category_pagination_engine,
        "_probe_boundary_page",
        fail_probe,
    )

    result = category_pagination_engine._jsf_category_pages_with_probe(
        scraper,
        category_url,
        category_id=127,
        expected_count=25,
        category_html=category_html,
    )

    assert result == [category_url]


def test_boundary_probe_is_retained_when_expected_count_is_not_reached(monkeypatch):
    scraper = _new_scraper()
    category_url = (
        "https://stock.importacionesfacundo.com/"
        "categoria-producto/catalogo/"
    )
    category_html = _products(1, 25)
    probe_called = False

    monkeypatch.setattr(
        category_pagination_engine,
        "_initial_jsf_page",
        lambda *args, **kwargs: (30, 2, category_html),
    )
    monkeypatch.setattr(
        category_pagination_engine,
        "_walk_jsf_page_batch",
        lambda *args, **kwargs: {
            2: (29, 2, _products(26, 4)),
        },
    )

    def record_probe(*args, **kwargs):
        nonlocal probe_called
        probe_called = True
        return False, set(), 0, 0

    monkeypatch.setattr(
        category_pagination_engine,
        "_probe_boundary_page",
        record_probe,
    )

    result = category_pagination_engine._jsf_category_pages_with_probe(
        scraper,
        category_url,
        category_id=127,
        expected_count=30,
        category_html=category_html,
    )

    assert probe_called is True
    assert result == [
        category_url,
        f"{category_url.rstrip('/')}?product-page=2",
    ]
