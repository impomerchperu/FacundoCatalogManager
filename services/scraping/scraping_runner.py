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
        owned_resources=None,
    ):
        self.scraping_service = scraping_service
        self.config = config
        self.category_service = category_service
        self.history_repository = history_repository
        self.catalog_repository = catalog_repository
        self._owned_resources = tuple(owned_resources or ())
        self._closed = False

    def close(self) -> None:
        """Libera el pipeline completo una sola vez, incluido cualquier recurso propio."""
        if self._closed:
            return
        self._closed = True

        close_scraper_service = getattr(self.scraping_service, "close", None)
        if callable(close_scraper_service):
            try:
                close_scraper_service()
            except Exception as error:  # noqa: BLE001
                _log_timing(
                    "SCRAPING TIMING | stage=resource_close_error | owner=scraping_service "
                    "| error_type=%s | error=%s",
                    type(error).__name__,
                    str(error),
                )
        else:
            legacy_scraper_service = getattr(
                self.scraping_service,
                "scraper_service",
                None,
            )
            close_legacy_scraper = getattr(legacy_scraper_service, "close", None)
            if callable(close_legacy_scraper):
                try:
                    close_legacy_scraper()
                except Exception as error:  # noqa: BLE001
                    _log_timing(
                        "SCRAPING TIMING | stage=resource_close_error | owner=legacy_scraper_service "
                        "| error_type=%s | error=%s",
                        type(error).__name__,
                        str(error),
                    )

        closed_ids: set[int] = set()
        for resource in reversed(self._owned_resources):
            if id(resource) in closed_ids:
                continue
            closed_ids.add(id(resource))
            close = getattr(resource, "close", None)
            if not callable(close):
                continue
            try:
                close()
            except Exception as error:  # noqa: BLE001
                _log_timing(
                    "SCRAPING TIMING | stage=resource_close_error | owner=%s "
                    "| error_type=%s | error=%s",
                    type(resource).__name__,
                    type(error).__name__,
                    str(error),
                )

    def run(
        self,
        categories: list[Category] | None = None,
        progress_callback=None,
        *,
        full_catalog=False,
    ):
        """Ejecuta scraping sobre las categorías recibidas."""
        if categories is None:
            return self.run_all(progress_callback)

        started = time.perf_counter()
        _log_timing(
            "SCRAPING TIMING | stage=run_start | categories=%d",
            len(categories),
        )
        self._prepare_run(full_catalog)

        try:
            return self._execute_categories(categories, progress_callback)
        except Exception as error:
            self._log_run_error(categories, error)
            raise
        finally:
            _log_timing(
                "SCRAPING TIMING | stage=run_total | categories=%d "
                "| seconds=%.3f",
                len(categories),
                time.perf_counter() - started,
            )

    def _prepare_run(self, full_catalog: bool) -> None:
        reset_sync_result = getattr(
            self.scraping_service,
            "reset_sync_result",
            None,
        )
        if callable(reset_sync_result):
            reset_sync_result()

        set_scraping_mode = getattr(self.scraping_service, "set_scraping_mode", None)
        if callable(set_scraping_mode):
            set_scraping_mode("full" if full_catalog else "directed")
            return

        self.scraping_service._scraping_mode = "full" if full_catalog else "directed"

    def _execute_categories(self, categories, progress_callback):
        sync_categories = getattr(
            self.scraping_service,
            "sync_categories",
            None,
        )
        if callable(sync_categories):
            return self._execute_sync_categories(
                sync_categories,
                categories,
                progress_callback,
            )
        return self._execute_legacy_categories(categories, progress_callback)

    @staticmethod
    def _execute_sync_categories(
        sync_categories,
        categories,
        progress_callback,
    ):
        pipeline_total = max(len(categories) * 2, 1)

        def pipeline_progress(current, _total):
            if progress_callback:
                progress_callback(
                    min(max(int(current), 0), len(categories)),
                    pipeline_total,
                )

        result = sync_categories(categories, pipeline_progress)
        if progress_callback:
            progress_callback(pipeline_total, pipeline_total)
        return result

    def _execute_legacy_categories(self, categories, progress_callback):
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

    @staticmethod
    def _log_run_error(categories, error) -> None:
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

    def run_all(self, progress_callback=None):
        """Obtiene categorías automáticamente y ejecuta FULL solo con cobertura total."""
        if self.category_service is None:
            return []

        started = time.perf_counter()
        discovered_categories = list(self.category_service.scrape_all() or [])
        categories = discovered_categories
        category_filter = getattr(
            self.config,
            "is_category_enabled",
            None,
        )
        if callable(category_filter):
            categories = [
                category
                for category in discovered_categories
                if category_filter(getattr(category, "name", ""))
            ]
        _log_timing(
            "SCRAPING TIMING | stage=category_discovery | categories=%d "
            "| seconds=%.3f",
            len(categories),
            time.perf_counter() - started,
        )

        full_catalog = len(categories) == len(discovered_categories)
        if not full_catalog:
            _log_timing(
                "SCRAPING TIMING | stage=category_filter | "
                "discovered=%d | selected=%d | mode=directed",
                len(discovered_categories),
                len(categories),
            )

        return self.run(
            categories,
            progress_callback,
            full_catalog=full_catalog,
        )
