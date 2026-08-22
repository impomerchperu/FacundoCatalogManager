import time
import traceback
from pathlib import Path

from models.scraping.category import Category
from repositories.product_repository import ProductRepository
from repositories.scraping.scraping_history_repository import (
    ScrapingHistoryRepository,
)
from services.scraping.category_service import CategoryService

PROJECT_ROOT = Path(__file__).resolve().parents[2]
TIMING_LOG = PROJECT_ROOT / "data" / "scraping_timing.log"


def _log_timing(message, *args):
    TIMING_LOG.parent.mkdir(parents=True, exist_ok=True)
    formatted = message % args if args else message
    with TIMING_LOG.open("a", encoding="utf-8") as file:
        file.write(f"{formatted}\n")


class ScrapingRunner:
    """Ejecuta y coordina el proceso completo de scraping."""

    def __init__(
        self,
        scraping_service,
        config=None,
        category_service: CategoryService | None = None,
        history_repository: ScrapingHistoryRepository | None = None,
        catalog_repository: ProductRepository | None = None,
    ):
        self.scraping_service = scraping_service
        self.config = config
        self.category_service = category_service
        self.history_repository = history_repository
        self.catalog_repository = catalog_repository

    def run(
        self,
        categories: list[Category] | None = None,
        progress_callback=None,
    ):
        """Ejecuta scraping sobre las categorías recibidas."""
        if categories is None:
            return self.run_all(progress_callback)

        started = time.perf_counter()
        _log_timing(
            "SCRAPING TIMING | stage=run_start | categories=%d",
            len(categories),
        )

        reset_sync_result = getattr(
            self.scraping_service,
            "reset_sync_result",
            None,
        )
        if callable(reset_sync_result):
            reset_sync_result()

        try:
            sync_categories = getattr(
                self.scraping_service,
                "sync_categories",
                None,
            )
            if callable(sync_categories):
                return sync_categories(categories, progress_callback)

            results = []
            total = len(categories)

            for index, category in enumerate(categories, start=1):
                if hasattr(self.scraping_service, "sync_category"):
                    products = self.scraping_service.sync_category(
                        category.url,
                        category.name,
                    )
                else:
                    products = self.scraping_service.scrape_category(category)

                results.extend(products)
                if progress_callback:
                    progress_callback(index, total)
            return results
        except Exception as error:
            _log_timing(
                "SCRAPING TIMING | stage=run_error | categories=%d | "
                "error_type=%s | error=%s",
                len(categories),
                type(error).__name__,
                str(error),
            )
            traceback_text = "".join(
                traceback.format_exception(type(error), error, error.__traceback__)
            ).rstrip()
            for line in traceback_text.splitlines():
                _log_timing("SCRAPING TIMING | stage=run_traceback | %s", line)
            raise
        finally:
            _log_timing(
                "SCRAPING TIMING | stage=run_total | categories=%d "
                "| seconds=%.3f",
                len(categories),
                time.perf_counter() - started,
            )

    def run_all(self, progress_callback=None):
        """Obtiene categorías automáticamente y ejecuta el scraping completo."""
        if self.category_service is None:
            return []

        started = time.perf_counter()
        categories = self.category_service.scrape_all()
        _log_timing(
            "SCRAPING TIMING | stage=category_discovery | categories=%d "
            "| seconds=%.3f",
            len(categories),
            time.perf_counter() - started,
        )

        return self.run(categories, progress_callback)
