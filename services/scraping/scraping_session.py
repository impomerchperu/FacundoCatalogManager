from dataclasses import dataclass, field
from datetime import datetime, timezone

from models.scraping.scraping_history import ScrapingHistory


@dataclass
class ScrapingSessionResult:
    """
    Resultado de una ejecución completa
    de scraping.
    """

    started_at: datetime | None = None

    finished_at: datetime | None = None

    processed: int = 0

    created: int = 0

    updated: int = 0

    unchanged: int = 0

    errors: list[str] = field(
        default_factory=list,
    )

    products: list = field(
        default_factory=list,
    )

    def success(self) -> bool:
        return len(self.errors) == 0

    def status(self) -> str:
        if self.success():
            return "SUCCESS"

        return "ERROR"


class ScrapingSession:
    """
    Controlador de una sesión completa
    de scraping.

    Además de ejecutar el proceso, registra
    automáticamente cada ejecución en el
    historial persistente.
    """

    def __init__(
        self,
        runner,
        history_repository=None,
    ):
        self.runner = runner

        self.history_repository = (
            history_repository
        )

        self.result = ScrapingSessionResult()

    def execute(
        self,
        categories=None,
        progress_callback=None,
    ):
        self.result = ScrapingSessionResult()

        self.result.started_at = datetime.now(
            timezone.utc,
        )

        try:
            products = self.runner.run(
                categories or [],
                progress_callback,
            )

            self.result.products = products

            self.result.processed = len(
                products,
            )

            self._extract_sync_result()

        except RuntimeError as error:
            self.result.errors.append(
                str(error),
            )

        self.result.finished_at = datetime.now(
            timezone.utc,
        )

        self._save_history()

        return self.result

    def execute_all(
        self,
        progress_callback=None,
    ):
        self.result = ScrapingSessionResult()

        self.result.started_at = datetime.now(
            timezone.utc,
        )

        try:
            products = self.runner.run_all(
                progress_callback,
            )

            self.result.products = products

            self.result.processed = len(
                products,
            )

            self._extract_sync_result()

        except RuntimeError as error:
            self.result.errors.append(
                str(error),
            )

        self.result.finished_at = datetime.now(
            timezone.utc,
        )

        self._save_history()

        return self.result

    def _extract_sync_result(self):
        service = self.runner.scraping_service

        sync_result = getattr(
            service,
            "last_sync_result",
            None,
        )

        if sync_result is None:
            return

        self.result.created = (
            sync_result.created
        )

        self.result.updated = (
            sync_result.updated
        )

        self.result.unchanged = (
            sync_result.unchanged
        )

        self.result.errors.extend(
            sync_result.errors,
        )

    def _save_history(self):
        if self.history_repository is None:
            return

        if (
            self.result.started_at is None
            or self.result.finished_at is None
        ):
            return

        message = (
            "Actualización de catálogo "
            "completada correctamente."
            if self.result.success()
            else (
                "Actualización de catálogo "
                "finalizada con errores."
            )
        )

        if self.result.errors:
            message = (
                f"{message} "
                f"Errores registrados: "
                f"{len(self.result.errors)}."
            )

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

        self.history_repository.save(
            history,
        )
