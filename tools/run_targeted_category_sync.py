"""Run a bounded, directed sync for one category to verify cache-write locking.

This utility never starts a full-catalog sync and refuses categories whose live
expected product count exceeds the configured safety limit.
"""

from __future__ import annotations

import time
from pathlib import Path

from controllers.scraping_controller import ScrapingController
from services.scraping.category_name_normalizer import normalize_category_name

PROJECT_ROOT = Path(__file__).resolve().parents[1]
TIMING_LOG = PROJECT_ROOT / "data" / "scraping_timing.log"
TARGET_CATEGORY = "Kits de Herramientas"
MAX_EXPECTED_PRODUCTS = 10


def main() -> int:
    controller = ScrapingController()
    try:
        runner = controller.session.runner
        category_service = getattr(runner, "category_service", None)
        if category_service is None:
            print("ERROR: el runner no expone category_service.")
            return 2

        discovery_started = time.perf_counter()
        categories = list(category_service.scrape_all() or [])
        print(
            "Descubrimiento de categorías: "
            f"{time.perf_counter() - discovery_started:.2f} s"
        )

        target_key = normalize_category_name(TARGET_CATEGORY)
        category = next(
            (
                item
                for item in categories
                if normalize_category_name(getattr(item, "name", "")) == target_key
            ),
            None,
        )
        if category is None:
            names = ", ".join(
                str(getattr(item, "name", "")) for item in categories
            )
            print(f"ERROR: categoría no encontrada: {TARGET_CATEGORY}")
            print(f"Categorías detectadas: {names or '(ninguna)'}")
            return 2

        expected_count = max(int(getattr(category, "expected_count", 0) or 0), 0)
        print(f"Categoría: {category.name}")
        print(f"URL: {category.url}")
        print(f"Productos esperados: {expected_count}")

        if expected_count > MAX_EXPECTED_PRODUCTS:
            print(
                "CANCELADO: la categoría supera el límite de seguridad "
                f"({MAX_EXPECTED_PRODUCTS} productos esperados)."
            )
            return 2

        scraping_service = runner.scraping_service
        browser_getter = getattr(scraping_service, "_browser", None)
        browser = browser_getter() if callable(browser_getter) else None
        if browser is None:
            print("ERROR: no se pudo localizar el navegador del scraping.")
            return 2

        # Revalidate cache entries against the origin during this targeted run.
        browser._force_source_page_revalidation = True

        log_offset = TIMING_LOG.stat().st_size if TIMING_LOG.exists() else 0
        sync_started = time.perf_counter()
        result = controller.run_scraping(categories=[category])
        print(f"Duración de sincronización: {time.perf_counter() - sync_started:.2f} s")

        errors = list(getattr(result, "errors", []) or [])
        status_getter = getattr(result, "status", None)
        status = status_getter() if callable(status_getter) else "UNKNOWN"
        print(f"Estado: {status}")
        for field in (
            "categories_processed",
            "products_found",
            "products_unique",
            "processed",
            "created",
            "updated",
            "unchanged",
        ):
            print(f"{field}: {getattr(result, field, 0)}")

        print(f"errors: {len(errors)}")
        for error in errors:
            print(f"ERROR: {error}")

        if TIMING_LOG.exists():
            appended = TIMING_LOG.read_bytes()[log_offset:].decode(
                "utf-8",
                errors="replace",
            )
            relevant_stages = (
                "source_page_cache_collection",
                "gallery_source_page_cache",
                "gallery_sync",
                "run_total",
                "run_error",
            )
            metrics = [
                line
                for line in appended.splitlines()
                if any(stage in line for stage in relevant_stages)
            ]
            if metrics:
                print("Métricas de esta ejecución:")
                for line in metrics:
                    print(line)

        success = getattr(result, "success", None)
        if callable(success):
            return 0 if success() and not errors else 1
        return 0 if not errors else 1
    finally:
        controller.close()


if __name__ == "__main__":
    raise SystemExit(main())
