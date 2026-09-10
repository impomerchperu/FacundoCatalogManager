from models.scraping.category import Category
from models.scraping.sync_result import SyncResult
from services.scraping.category_product_sync_service import CategoryProductSyncService
from services.scraping.normalized_category_product_sync_service import (
    NormalizedCategoryProductSyncService,
)


class FakeNormalizedRepository:
    def __init__(self):
        self.modes = []

    def start_run(self, *, mode, categories_requested, expected_category_occurrences):
        self.modes.append(mode)
        return 1

    def persist_occurrences(
        self,
        run_id,
        categories,
        products,
        product_repository,
        occurrence_metadata=None,
    ):
        return 0

    def finish_run(
        self,
        run_id,
        *,
        result,
        actual_category_occurrences,
        message="",
    ):
        return None


def _build_service(repository):
    class ScraperService:
        scraper = None

    class CatalogSyncService:
        repository = object()

    service = NormalizedCategoryProductSyncService(
        ScraperService(),
        persistence_service=None,
        catalog_sync_service=CatalogSyncService(),
        normalized_repository=repository,
    )
    service.last_sync_result = SyncResult()
    return service


def test_normalized_sync_categories_defaults_to_directed(monkeypatch):
    repository = FakeNormalizedRepository()
    service = _build_service(repository)

    monkeypatch.setattr(
        CategoryProductSyncService,
        "sync_categories",
        lambda self, categories, progress_callback=None: [],
    )

    service.sync_categories([Category(name="Categoría A", url="https://example.test/a")])

    assert repository.modes == ["directed"]


def test_normalized_sync_categories_uses_full_mode_when_runner_marks_full():
    repository = FakeNormalizedRepository()
    service = _build_service(repository)
    service._scraping_mode = "full"

    service._persist_normalized(
        [Category(name="Categoría A", url="https://example.test/a")],
        [],
        mode=service._scraping_mode,
    )

    assert repository.modes == ["full"]


def test_full_mode_skips_normalized_persistence_when_coverage_is_incomplete():
    repository = FakeNormalizedRepository()
    service = _build_service(repository)
    service._scraping_mode = "full"
    service.last_sync_result = SyncResult(
        expected_category_occurrences=10,
        products_found=8,
        products_unique=8,
    )
    service.last_sync_result.category_summary = [
        {
            "category": "Categoría A",
            "expected": 10,
            "products": 8,
            "unique_products": 8,
            "gap": 2,
        }
    ]

    service._persist_normalized(
        [Category(name="Categoría A", url="https://example.test/a", expected_count=10)],
        [type("Product", (), {"code": "FB-001"})()],
        mode="full",
    )

    assert repository.modes == []


def test_occurrence_metadata_uses_normalized_category_keys_and_preserves_multi_category_products():
    repository = FakeNormalizedRepository()
    service = _build_service(repository)

    class Scraper:
        def get_page_metrics(self):
            return {
                "https://example.test/cocina/": {
                    "pages": [
                        {"page": 1, "unique_products": 1},
                    ]
                },
                "https://example.test/oficina/": {
                    "pages": [
                        {"page": 2, "unique_products": 1},
                    ]
                },
            }

    service.scraper_service.scraper = Scraper()
    categories = [
        Category(name="Cocina", url="https://example.test/cocina/"),
        Category(name="Oficina", url="https://example.test/oficina/"),
    ]
    products = [
        type(
            "Product",
            (),
            {
                "code": "FB-1000",
                "category": "Cocina, Oficina",
            },
        )()
    ]

    metadata = service._build_occurrence_metadata(categories, products)

    assert metadata == {
        ("cocina mesa y hogar", "fb-1000"): (1, 1),
        ("oficina", "fb-1000"): (2, 1),
    }
