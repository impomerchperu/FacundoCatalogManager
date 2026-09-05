from dataclasses import dataclass, field
from datetime import datetime, timezone

from models.scraping.scraping_history import ScrapingHistory


@dataclass
class ScrapingSessionResult:
    """Resultado de una ejecución completa de scraping."""

    started_at: datetime | None = None
    finished_at: datetime | None = None
    processed: int = 0
    created: int = 0
    updated: int = 0
    unchanged: int = 0
    deleted: int = 0
    generated: int = 0
    products_expected: int = 0
    products_found: int = 0
    products_unique: int = 0
    products_multiple_categories: int = 0
    duplicate_occurrences: int = 0
    category_summary: list[dict] = field(default_factory=list)
    multiple_category_products: list[dict] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    products: list = field(default_factory=list)
    changes: list[dict] = field(default_factory=list)
    history_id: int | None = None

    @property
    def classified_total(self) -> int:
        return self.created + self.updated + self.unchanged

    @property
    def counts_are_consistent(self) -> bool:
        return self.classified_total == self.products_unique

    def success(self) -> bool:
        return not self.errors

    def status(self) -> str:
        return "SUCCESS" if self.success() else "ERROR"


class ScrapingSession:
    """Coordina scraping, aplicación automática y registro de cambios."""

    def __init__(self, runner, history_repository=None, catalog_repository=None):
        self.runner = runner
        self.history_repository = history_repository
        self.catalog_repository = catalog_repository
        self.result = ScrapingSessionResult()

    def execute(self, categories=None, progress_callback=None):
        return self._execute(lambda: self.runner.run(categories or [], progress_callback))

    def execute_all(self, progress_callback=None):
        return self._execute(lambda: self.runner.run_all(progress_callback))

    def _execute(self, operation):
        self.result = ScrapingSessionResult(started_at=datetime.now(timezone.utc))
        db = getattr(self.history_repository, "db", None)
        transaction_started = False
        try:
            if db is not None:
                db.begin()
                transaction_started = True
            products = operation()
            self.result.products = products or []
            self._extract_sync_result()
            if not self.result.counts_are_consistent:
                self.result.errors.append(
                    "Inconsistencia en el resumen de sincronización: "
                    f"procesados={self.result.processed}, "
                    f"clasificados={self.result.classified_total}, "
                    f"únicos={self.result.products_unique}."
                )
            if self.result.errors and not self._only_coverage_error():
                self._rollback_transaction(db, transaction_started)
                transaction_started = False
                self.result.finished_at = datetime.now(timezone.utc)
                self._write_error_result_artifact()
                self._save_history_in_clean_transaction(db)
                return self.result
            self._persist_catalog_products()
            self.result.finished_at = datetime.now(timezone.utc)
            if db is not None and transaction_started:
                db.commit()
                transaction_started = False
            try:
                self._save_history_in_clean_transaction(db)
            except Exception as history_error:  # noqa: BLE001
                self.result.errors.append(
                    "No se pudo registrar el historial de cambios; "
                    "los cambios del catálogo ya fueron aplicados: "
                    f"{history_error}"
                )
        except Exception as error:  # noqa: BLE001
            self._rollback_transaction(db, transaction_started)
            transaction_started = False
            self.result.errors.append(str(error))
            self.result.finished_at = datetime.now(timezone.utc)
            self._write_error_result_artifact()
            try:
                self._save_history_in_clean_transaction(db)
            except Exception as history_error:  # noqa: BLE001
                self.result.errors.append(
                    f"No se pudo registrar el historial del error: {history_error}"
                )
        return self.result

    def _only_coverage_error(self):
        coverage_errors = [
            error
            for error in self.result.errors
            if str(error).startswith("Cobertura del catálogo incompleta:")
        ]
        return bool(coverage_errors) and len(coverage_errors) == len(self.result.errors)

    @staticmethod
    def _rollback_transaction(db, transaction_started):
        if db is not None and transaction_started:
            db.rollback()

    def _save_history_in_clean_transaction(self, db):
        if db is None:
            self._save_history()
            return
        try:
            db.begin()
            self._save_history()
            db.commit()
        except Exception:
            db.rollback()
            raise

    def _write_error_result_artifact(self):
        sync_service = getattr(self.runner, "scraping_service", None)
        catalog_sync = getattr(sync_service, "catalog_sync_service", None)
        writer = getattr(catalog_sync, "result_writer", None)
        result = getattr(catalog_sync, "last_sync_result", None)
        if writer is None or result is None:
            return
        result.errors = list(dict.fromkeys([*result.errors, *self.result.errors]))
        result.finished_at = self.result.finished_at
        result.success = False
        codes = {
            str(getattr(product, "code", "")).strip().upper().casefold()
            for product in self.result.products
            if str(getattr(product, "code", "")).strip()
        }
        writer.write(result, codes)

    def _persist_catalog_products(self):
        if self.catalog_repository is None:
            return
        sync_service = getattr(self.runner, "scraping_service", None)
        catalog_sync_service = getattr(sync_service, "catalog_sync_service", None)
        if catalog_sync_service is not None:
            return
        for product in self.result.products:
            self.catalog_repository.save(product)

    def _extract_sync_result(self):
        sync_service = self.runner.scraping_service
        sync_result = getattr(sync_service, "last_sync_result", None)
        catalog_sync = getattr(sync_service, "catalog_sync_service", None)
        catalog_result = getattr(catalog_sync, "last_sync_result", None)
        if sync_result is None:
            self.result.processed = len(self.result.products)
            self.result.products_expected = 0
            self.result.products_found = self.result.processed
            self.result.products_unique = self.result.processed
            return
        self.result.processed = sync_result.processed
        self.result.created = sync_result.created
        self.result.updated = sync_result.updated
        self.result.unchanged = sync_result.unchanged
        self.result.deleted = sync_result.deleted
        self.result.generated = sync_result.generated
        self.result.changes = list(sync_result.changes)
        self.result.errors.extend(sync_result.errors)
        coverage_result = sync_result
        if (
            getattr(coverage_result, "expected_category_occurrences", 0) <= 0
            and catalog_result is not None
        ):
            coverage_result = catalog_result
        self.result.products_expected = getattr(coverage_result, "products_expected", 0)
        self.result.products_found = getattr(coverage_result, "products_found", len(self.result.products))
        self.result.products_unique = getattr(coverage_result, "products_unique", len(self.result.products))
        self.result.products_multiple_categories = getattr(coverage_result, "products_multiple_categories", 0)
        self.result.duplicate_occurrences = getattr(coverage_result, "duplicate_occurrences", 0)
        self.result.category_summary = list(getattr(coverage_result, "category_summary", []))
        self.result.multiple_category_products = list(getattr(coverage_result, "multiple_category_products", []))
        if not coverage_result.coverage_complete:
            self.result.errors.append(
                "Cobertura del catálogo incompleta: "
                f"esperados={coverage_result.expected_category_occurrences}, "
                f"encontrados={coverage_result.products_found}, "
                f"brecha={coverage_result.category_occurrence_gap}."
            )

    def _save_history(self):
        if self.history_repository is None:
            return
        if self.result.started_at is None or self.result.finished_at is None:
            return
        message = (
            "Descarga completada y cambios aplicados automáticamente."
            if self.result.success()
            else "Descarga finalizada con advertencias; cambios detectados aplicados."
        )
        history = ScrapingHistory(
            started_at=self.result.started_at,
            finished_at=self.result.finished_at,
            processed=self.result.processed,
            created=self.result.created,
            updated=self.result.updated,
            unchanged=self.result.unchanged,
            deleted=self.result.deleted,
            generated=self.result.generated,
            products_expected=self.result.products_expected,
            products_found=self.result.products_found,
            products_unique=self.result.products_unique,
            products_multiple_categories=self.result.products_multiple_categories,
            duplicate_occurrences=self.result.duplicate_occurrences,
            category_summary=self.result.category_summary,
            multiple_category_products=self.result.multiple_category_products,
            errors=len(self.result.errors),
            status=self.result.status(),
            message=message,
        )
        self.result.history_id = self.history_repository.save(
            history,
            self.result.changes,
            self.result.products,
        )
