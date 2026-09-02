from threading import RLock

from scrapers.collectors import page_metrics_patch
from scrapers.collectors.product_collection_scraper import ProductCollectionScraper


def test_page_metrics_audit_logs_every_category_page(tmp_path):
    scraper = object.__new__(ProductCollectionScraper)
    scraper._page_metrics = {}
    scraper._page_metrics_lock = RLock()
    log_path = tmp_path / "scraping_timing.log"
    original_log = page_metrics_patch.TIMING_LOG
    page_metrics_patch.TIMING_LOG = log_path
    try:
        page_metrics_patch._store_page_metrics_with_audit(
            scraper,
            category_url="https://stock.importacionesfacundo.com/categoria-producto/demo/",
            category_name="Demo",
            expected_count=51,
            pages=[
                {
                    "page": 1,
                    "url": "https://stock.importacionesfacundo.com/categoria-producto/demo/",
                    "html_available": True,
                    "cards": 25,
                    "unique_products": 25,
                },
                {
                    "page": 2,
                    "url": "https://stock.importacionesfacundo.com/categoria-producto/demo?product-page=2",
                    "html_available": True,
                    "cards": 25,
                    "unique_products": 25,
                },
                {
                    "page": 3,
                    "url": "https://stock.importacionesfacundo.com/categoria-producto/demo?product-page=3",
                    "html_available": True,
                    "cards": 1,
                    "unique_products": 1,
                },
            ],
            unique_products=51,
        )
    finally:
        page_metrics_patch.TIMING_LOG = original_log

    content = log_path.read_text(encoding="utf-8")
    assert "stage=category_page_summary" in content
    assert "category=Demo | pages_expected=3 | pages_requested=3 | pages_loaded=3 | cards=51 | unique=51" in content
    assert "category=Demo | page=1 | cards=25 | unique=25" in content
    assert "category=Demo | page=2 | cards=25 | unique=25" in content
    assert "category=Demo | page=3 | cards=1 | unique=1" in content
