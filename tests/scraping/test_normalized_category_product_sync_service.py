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
