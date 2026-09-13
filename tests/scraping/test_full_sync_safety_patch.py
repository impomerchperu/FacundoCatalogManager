from types import SimpleNamespace

from models.scraping.sync_result import SyncResult
from scrapers.collectors import full_sync_safety_patch  # noqa: F401
from services.scraping.category_product_sync_service import CategoryProductSyncService


class Product:
    code = "FB-001"
    name = "Producto 1"
    category = "Categoria"


class IdentityMapper:
    @staticmethod
    def map(product):
        return product


class RecordingCatalogSync:
    def __init__(self):
        self.calls = 0
        self.full_calls = 0

    @staticmethod
    def consolidate_products(products):
        return list(products)

    def sync(self, products, **kwargs):
        self.calls += 1
        result = SyncResult(
            processed=len(products),
            unchanged=len(products),
            products_found=len(products),
            products_unique=len(products),
        )
        result.finish()
        return result

    def sync_full_catalog(self, products, **kwargs):
        self.full_calls += 1
        result = SyncResult(
            processed=len(products),
            unchanged=len(products),
            products_found=len(products),
            products_unique=len({
                str(getattr(product, "code", "")).strip().casefold()
                for product in products
                if str(getattr(product, "code", "")).strip()
            }),
        )
        result.finish()
        return result


def _service(catalog_sync):
    return CategoryProductSyncService(
        scraper_service=object(),
        persistence_service=object(),
        mapper=IdentityMapper(),
        catalog_sync_service=catalog_sync,
    )


def test_incomplete_full_sync_does_not_write_catalog():
    catalog_sync = RecordingCatalogSync()
    service = _service(catalog_sync)
    service._full_sync_coverage_validated = False
    service._full_sync_coverage_reason = "terminal_http_errors:1"

    products = [Product()]
    result = service.sync_products(
        products,
        full_sync=True,
        allow_prune=False,
        expected_products=1,
        expected_category_occurrences=1,
    )

    assert len(result) == len(products)
    assert result[0].code == products[0].code
    assert catalog_sync.calls == 0
    assert catalog_sync.full_calls == 0
    assert service.last_sync_result.errors == [
        "Cobertura del catálogo incompleta: "
        "sincronización FULL omitida por seguridad (terminal_http_errors:1)."
    ]


def test_complete_full_sync_still_writes_catalog_without_prune():
    catalog_sync = RecordingCatalogSync()
    service = _service(catalog_sync)
    service._full_sync_coverage_validated = True
    service._full_sync_coverage_reason = "complete"

    products = [Product()]
    result = service.sync_products(
        products,
        full_sync=True,
        allow_prune=False,
        expected_products=1,
        expected_category_occurrences=1,
    )

    assert len(result) == len(products)
    assert result[0].code == products[0].code
    assert catalog_sync.calls == 1
    assert catalog_sync.full_calls == 0


def test_final_complete_coverage_overrides_recovered_guard_state():
    catalog_sync = RecordingCatalogSync()
    service = _service(catalog_sync)
    service._full_sync_coverage_validated = False
    service._full_sync_coverage_reason = "terminal_http_errors:1"
    service.last_sync_result = SyncResult(
        processed=1,
        unchanged=1,
        products_expected=1,
        products_found=1,
        products_unique=1,
    )
    service.last_sync_result.category_summary = [
        {
            "category": "Categoria",
            "expected": 1,
            "products": 1,
            "unique_products": 1,
            "gap": 0,
        }
    ]
    service.last_sync_result.finish()

    products = [Product()]
    result = service.sync_products(
        products,
        full_sync=True,
        allow_prune=False,
        expected_products=1,
        expected_category_occurrences=1,
    )

    assert len(result) == len(products)
    assert result[0].code == products[0].code
    assert catalog_sync.calls == 0
    assert catalog_sync.full_calls == 1
    assert service.last_sync_result.errors == []


def test_terminal_http_error_is_ignored_when_category_coverage_is_complete():
    class Browser:
        @staticmethod
        def get_http_metrics():
            return {"http_terminal_errors": 1}

    class Scraper:
        browser = Browser()

    class ScraperService:
        scraper = Scraper()

    service = CategoryProductSyncService(
        scraper_service=ScraperService(),
        persistence_service=object(),
    )
    service.last_sync_result = SyncResult(
        expected_category_occurrences=2,
        products_found=2,
        products_unique=2,
    )
    service.last_sync_result.category_summary = [
        {
            "category": "Categoria",
            "expected": 2,
            "products": 2,
            "unique_products": 2,
            "gap": 0,
        }
    ]

    assert service._terminal_http_error_reason() is None


def test_real_full_coverage_534_occurrences_530_unique_allows_prune_recovery():
    catalog_sync = RecordingCatalogSync()
    service = _service(catalog_sync)
    service._full_sync_coverage_validated = False
    service._full_sync_coverage_reason = "terminal_http_errors:1"

    products = [
        SimpleNamespace(code=f"FB-{index + 1:04d}")
        for index in range(530)
    ]
    products.extend(
        SimpleNamespace(code=code)
        for code in ("FB-0001", "FB-0002", "FB-0003", "FB-0004")
    )
    service.last_sync_result = SyncResult(
        expected_category_occurrences=534,
        products_found=534,
        products_unique=530,
    )
    service.last_sync_result.category_summary = [
        {
            "category": "Grupo A",
            "expected": 267,
            "products": 267,
            "unique_products": 267,
            "gap": 0,
        },
        {
            "category": "Grupo B",
            "expected": 267,
            "products": 267,
            "unique_products": 267,
            "gap": 0,
        },
    ]

    result = service.sync_products(
        products,
        full_sync=True,
        allow_prune=False,
        expected_products=530,
        expected_category_occurrences=534,
    )

    assert len(result) == 534
    assert catalog_sync.calls == 0
    assert catalog_sync.full_calls == 1
    assert service._full_sync_coverage_validated is True
    assert service._full_sync_coverage_reason == "complete"
