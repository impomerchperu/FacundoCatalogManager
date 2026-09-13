from collections.abc import Callable

from controllers.scraping_controller import ScrapingController
from database.db_manager import DBManager
from services.catalog_history_recovery_service import CatalogHistoryRecoveryService
from services.catalog_reconciliation_service import CatalogReconciliationService


class CatalogBootstrapService:
    """Orquesta la reparación inicial sin iniciar ni ejecutar scraping web."""

    HISTORY_RECOVERY_KEY = "history_recovery_applied"

    def __init__(
        self,
        db: DBManager | None = None,
        controller_factory: Callable[[], ScrapingController] = ScrapingController,
    ) -> None:
        self.db = db or DBManager()
        self.controller_factory = controller_factory
        self.reconciliation_service = CatalogReconciliationService(self.db)
        self.history_recovery_service = CatalogHistoryRecoveryService(self.db)

    def is_initialized(self) -> bool:
        row = self.db.fetch_all(
            "SELECT value FROM catalog_metadata WHERE key=?", ("initialized",)
        )
        return bool(row and row[0]["value"] == "1")

    def product_count(self) -> int:
        row = self.db.fetch_all("SELECT COUNT(*) AS total FROM products")
        return int(row[0]["total"]) if row else 0

    def is_ready(self) -> bool:
        return self.is_initialized() or self.product_count() > 0

    def mark_initialized(self) -> None:
        self.db.execute_query(
            """
            INSERT INTO catalog_metadata (key, value)
            VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value=excluded.value
            """,
            ("initialized", "1"),
        )

    def _history_recovery_applied(self) -> bool:
        row = self.db.fetch_one(
            "SELECT value FROM catalog_metadata WHERE key=?",
            (self.HISTORY_RECOVERY_KEY,),
        )
        return bool(row and row["value"] == "1")

    def _mark_history_recovery_applied(self) -> None:
        self.db.execute_query(
            """
            INSERT INTO catalog_metadata (key, value)
            VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value=excluded.value
            """,
            (self.HISTORY_RECOVERY_KEY, "1"),
        )

    def _find_latest_successful_full_run(self):
        """Compatibilidad interna; la consulta vive en el reconciliador dedicado."""
        return self.reconciliation_service.find_latest_successful_full_run()

    def reconcile_latest_successful_run(self) -> int:
        """Reconstruye el catálogo desde la última ejecución FULL válida."""
        return self.reconciliation_service.reconcile_latest_successful_run()

    def reconcile_reference_run(self) -> int:
        """Alias de compatibilidad para la reconciliación del último FULL válido."""
        return self.reconcile_latest_successful_run()

    def restore_from_change_history(self) -> int:
        """Compatibilidad para reconstruir desde cambios históricos exitosos."""
        if self.product_count() > 0:
            return 0

        self.db.begin()
        try:
            restored = self.history_recovery_service.restore(manage_transaction=False)
            if restored > 0:
                self.mark_initialized()
                self._mark_history_recovery_applied()
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return restored

    def bootstrap(self) -> int:
        """Repara instalaciones no validadas y deja intacto un catálogo ya consolidado."""
        count = self.product_count()
        if self.is_initialized():
            return count

        if count > 0 and self._find_latest_successful_full_run() is None:
            return count

        restored = self.reconcile_latest_successful_run()
        if restored <= 0 and count == 0:
            restored = self.restore_from_change_history()
        if restored > 0:
            self.mark_initialized()
            self._mark_history_recovery_applied()
            self.db.commit()
        return restored or count
