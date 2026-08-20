from models.scraping.scraped_product import ScrapedProduct
from services.scraping.category_product_sync_service import (
    CategoryProductSyncService,
)


class FakeBrowser:
    def __init__(self, terminal_errors=0):
        self.terminal_errors = terminal_errors

    def get_http_metrics(self):
        return {"http_terminal_errors": self.terminal_errors}


class FakeScraper:
    def __init__(self, browser):
        self.category_scraper = type("CategoryScraper", (), {"browser": browser})()


class FakeScrapingService:
    def __init__(self, browser):
        self.scraper = FakeScraper(browser)


def build_service(terminal_errors=0):
    return CategoryProductSyncService(
        FakeScrapingService(FakeBrowser(terminal_errors)),
        persistence_service=None,
    )


def test_prune_guard_blocks_missing_product_codes():
    service = build_service()
    products = [
        ScrapedProduct(code="P001", name="Completo"),
        ScrapedProduct(code="", name="Sin código"),
    ]

    allowed, reason = service._full_sync_prune_guard(products, 24)

    assert allowed is False
    assert reason == "missing_codes:1"


def test_prune_guard_blocks_terminal_http_errors():
    service = build_service(terminal_errors=1)
    products = [ScrapedProduct(code="P001", name="Completo")]

    allowed, reason = service._full_sync_prune_guard(products, 24)

    assert allowed is False
    assert reason == "terminal_http_errors:1"


def test_prune_guard_blocks_category_coverage_gap():
    service = build_service()
    products = [
        ScrapedProduct(code="P001", name="Uno"),
        ScrapedProduct(code="P002", name="Dos"),
    ]

    allowed, reason = service._full_sync_prune_guard(
        products,
        24,
        expected_category_occurrences=3,
    )

    assert allowed is False
    assert reason == "category_coverage_gap:1"


def test_prune_guard_allows_complete_extraction():
    service = build_service()
    products = [
        ScrapedProduct(code="P001", name="Uno"),
        ScrapedProduct(code="P002", name="Dos"),
    ]

    allowed, reason = service._full_sync_prune_guard(products, 24)

    assert allowed is True
    assert reason == "complete"
