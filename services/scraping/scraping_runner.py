from __future__ import annotations

import time
import traceback
from pathlib import Path

TIMING_LOG = Path("data/scraping_timing.log")


def _log_timing(message: str, *args: object) -> None:
    TIMING_LOG.parent.mkdir(parents=True, exist_ok=True)
    with TIMING_LOG.open("a", encoding="utf-8") as handle:
        handle.write(message % args + "\n")


class ScrapingRunner:
    def __init__(self, scraping_service):
        self.scraping_service = scraping_service

    def run(self, categories, progress_callback=None):
        """Ejecuta el scraping para las categorías recibidas."""
        started = time.perf_counter()
        _log_timing(
            "SCRAPING TIMING | stage=run_start | categories=%d",
            len(categories),
        )
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
        else:
            return results
        finally:
            _log_timing(
                "SCRAPING TIMING | stage=run_total | categories=%d "
                "| seconds=%.3f",
                len(categories),
                time.perf_counter() - started,
            )

    def run_all(self, progress_callback=None):
        """Obtiene categorías automáticamente y ejecuta el scraping completo."""
        started = time.perf_counter()
        categories = self.scraping_service.category_service.scrape_all()
        _log_timing(
            "SCRAPING TIMING | stage=category_discovery | categories=%d "
            "| seconds=%.3f",
            len(categories),
            time.perf_counter() - started,
        )
        return self.run(categories, progress_callback)
