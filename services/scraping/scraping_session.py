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
    errors: list[str] = field(default_factory=list)
    products: list = field(default_factory=list)
    changes: list[dict] = field(default_factory=list)
    history_id: int | None = None

    @property
    def classified_total(self) -> int:
        """Total explicado por nuevos, actualizados y sin cambios."""
        return self.created + self.updated + self.unchanged

    @property
    def counts_are_consistent(self) -> bool:
        """Indica si los productos procesados están completamente clasificados."""
        return self.processed == self.classified_total

    def success(self) -> bool:
        return not self.errors

    def status(self) -> str:
        return "SUCCESS" if self.success() else "ERROR"


class ScrapingSession:
    """Coordina scraping, aplicación automática y registro de cambios."""

    def __init__(self, runner, history_repository=None):
        self.runner = runner
        self.history_repository = history_repository
        self.result = ScrapingSessionResult()

    def execute(self, categories=None, progress_callback=None):
        return self._execute(
            lambda: self.runner.run(categories or [], progress_callback),
        )

    def execute_all(self, progress_callback=None):
        return self._execute(
            lambda: self.runner.run_all(progress_callback),
        )

    def _execute(self, operation):
        self.result = ScrapingSessionResult(
            started_at=datetime.now(timezone.utc),
        )

        db = getattr(self.history_repository, "db", None)
        transaction_started = False

        try:
            if db is not None:
                db.begin()
                transaction_started = True

            products = operation()
            self.result.products = products
            self._extract_sync_result()

            if not self.result.counts_are_consistent:
                self.result.errors.append(
                    "Inconsistencia en el resumen de sincronización: "
                    f"procesados={self.result.processed}, "
                    f"clasificados={self.result.classified_total}."
                )

            if self.result.errors:
                if transaction_started:
                    db.rollback()
                    transaction_started = False
                self.result.finished_at = datetime.now(timezone.utc)
                self._save_history()
                return self.result

            self.result.finished_at = datetime.now(timezone.utc)
            self._save_history()

            if transaction_started:
                db.commit()
                transaction_started = False

        except Exception as error:  # noqa: BLE001
            if transaction_started:
                db.rollback()
                transaction_started = False
            self.result.errors.append(str(error))
            self.result.finished_at = datetime.now(timezone.utc)
            self._save_history()

        return self.result

    def _extract_sync_result(self):
        sync_result = getattr(
            self.runner.scraping_service,
            "last_sync_result",
            None,
        )
        if sync_result is None:
            return

        self.result.processed = sync_result.processed
        self.result.created = sync_result.created
        self.result.updated = sync_result.updated
        self.result.unchanged = sync_result.unchanged
        self.result.changes = list(sync_result.changes)
        self.result.errors.extend(sync_result.errors)

    def _save_history(self):
        if self.history_repository is None:
            return
        if self.result.started_at is None or self.result.finished_at is None:
            return

        if self.result.success():
            message = "Descarga completada y cambios aplicados automáticamente."
        else:
            message = "Descarga finalizada con errores; cambios revertidos."

        history = ScrapingHistory(
            started_at=self.result.started_at,
            finished_at=self.result.finished_at,
            processed=self.result.processed,
            created=self.result.created,
            updated=self.result.updated,
            unchanged=self.result.unchanged,
            errors=len(self.result.errors),
            status=self.result.status(),
            message=message,
        )

        self.result.history_id = self.history_repository.save(
            history,
            self.result.changes if self.result.success() else [],
            self.result.products if self.result.success() else [],
        )
