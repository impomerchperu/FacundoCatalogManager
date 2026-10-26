from types import SimpleNamespace

from services.scraping.scraping_session import ScrapingSession


class FakeDB:
    def __init__(self):
        self.operations = []
        self.transaction_active = False

    def begin(self):
        self.operations.append("begin")
        self.transaction_active = True

    def commit(self):
        self.operations.append("commit")
        self.transaction_active = False

    def rollback(self):
        self.operations.append("rollback")
        self.transaction_active = False


class FakeHistoryRepository:
    def __init__(self, db):
        self.db = db
        self.saved = []

    def save(self, history, changes, products):
        self.saved.append((history, changes, products))
        return 17


class FakeCatalogRepository:
    def __init__(self):
        self.saved = []

    def save(self, product):
        self.saved.append(product)


class FailingRunner:
    def run(self, categories, progress_callback=None):
        raise RuntimeError("fallo controlado")


class IncompleteRunner:
    def __init__(self, products):
        self.products = products
        self.scraping_service = SimpleNamespace(
            last_sync_result=SimpleNamespace(
                processed=len(products),
                created=0,
                updated=0,
                unchanged=len(products),
                deleted=0,
                generated=0,
                missing_code=0,
                changes=[],
                errors=[
                    "Cobertura del catálogo incompleta: sincronización FULL omitida por seguridad (terminal_http_errors:1)."
                ],
                coverage_complete=False,
                categories_processed=24,
                expected_category_occurrences=10,
                products_expected=9,
                products_found=len(products),
                products_unique=len(products),
            ),
            catalog_sync_service=None,
        )

    def run(self, categories, progress_callback=None):
        return list(self.products)


class Product:
    code = "TEST-001"
    name = "Producto de prueba"


def test_scraping_session_rolls_back_catalog_and_saves_error_history_cleanly():
    db = FakeDB()
    history_repository = FakeHistoryRepository(db)
    session = ScrapingSession(
        FailingRunner(),
        history_repository=history_repository,
    )

    result = session.execute(categories=[])

    assert result.status() == "ERROR"
    assert result.errors == ["fallo controlado"]
    assert result.history_id == 17
    assert len(history_repository.saved) == 1
    assert db.operations == ["begin", "rollback", "begin", "commit"]


def test_incomplete_coverage_never_persists_products_to_catalog_repository():
    db = FakeDB()
    history_repository = FakeHistoryRepository(db)
    catalog_repository = FakeCatalogRepository()
    session = ScrapingSession(
        IncompleteRunner([Product()]),
        history_repository=history_repository,
        catalog_repository=catalog_repository,
    )

    result = session.execute(categories=[])

    assert result.status() == "ERROR"
    assert result.success() is False
    assert catalog_repository.saved == []
    assert result.history_id == 17
    assert history_repository.saved[0][1] == []
    assert history_repository.saved[0][0].message == (
        "Descarga finalizada con cobertura incompleta; "
        "cambios del catálogo no aplicados."
    )
    assert db.operations == ["begin", "rollback", "begin", "commit"]


def test_scraping_session_flushes_source_cache_after_catalog_commit():
    db = FakeDB()
    flush_observations = []

    browser = SimpleNamespace(
        flush_source_page_cache=lambda: (
            flush_observations.append(db.transaction_active) or 1
        )
    )
    sync_result = SimpleNamespace(
        processed=0,
        created=0,
        updated=0,
        unchanged=0,
        deleted=0,
        generated=0,
        missing_code=0,
        changes=[],
        errors=[],
        coverage_complete=True,
        categories_processed=0,
        expected_category_occurrences=0,
        products_expected=0,
        products_found=0,
        products_unique=0,
        products_multiple_categories=0,
        duplicate_occurrences=0,
        category_summary=[],
        multiple_category_products=[],
    )
    scraping_service = SimpleNamespace(
        _browser=lambda: browser,
        last_sync_result=sync_result,
        catalog_sync_service=None,
        normalized_repository=None,
        image_sync_adapter=None,
    )

    class SuccessfulRunner:
        def __init__(self):
            self.scraping_service = scraping_service

        def run(self, categories, progress_callback=None):
            return []

    history_repository = FakeHistoryRepository(db)
    session = ScrapingSession(
        SuccessfulRunner(),
        history_repository=history_repository,
    )

    result = session.execute(categories=[])

    assert result.success() is True
    assert db.operations == ["begin", "commit"]
    assert flush_observations == [False]
