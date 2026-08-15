from collections.abc import Callable

from controllers.scraping_controller import ScrapingController
from database.db_manager import DBManager


class CatalogBootstrapService:
    """Garantiza una única base de catálogo inicial y persistente."""

    def __init__(
        self,
        db: DBManager | None = None,
        controller_factory: Callable[[], ScrapingController] = ScrapingController,
    ) -> None:
        self.db = db or DBManager()
        self.controller_factory = controller_factory

    def is_initialized(self) -> bool:
        row = self.db.fetch_all(
            "SELECT value FROM catalog_metadata WHERE key=?",
            ("initialized",),
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

    def bootstrap(self):
        """Realiza la carga inicial solo cuando el catálogo está vacío."""
        if self.is_initialized():
            return None

        if self.product_count() > 0:
            self.mark_initialized()
            self.db.commit()
            return None

        controller = self.controller_factory()
        result = controller.run_full_scraping()

        if result.success() and self.product_count() > 0:
            self.mark_initialized()
            self.db.commit()

        return result
