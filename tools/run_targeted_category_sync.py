"""Run a bounded, directed multi-category sync to check cache-write locking.

The utility never starts a full-catalog sync. It validates live category counts
and enforces per-category and total-product ceilings before writing anything.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from controllers.scraping_controller import ScrapingController
from services.scraping.category_name_normalizer import normalize_category_name

PROJECT_ROOT = Path(__file__).resolve().parents[1]
TIMING_LOG = PROJECT_ROOT / "data" / "scraping_timing.log"
TARGET_CATEGORIES = (
    "Kits de Herramientas",
    "Lapiceros Ecologicos",
    "Estuches",
    "Enmicadoras / Laminadoras",
)
MAX_EXPECTED_PER_CATEGORY = 120
MAX_TOTAL_EXPECTED_PRODUCTS = 600


def _discover_categories(category_service: Any) -> list[Any]:
    started = time.perf_counter()
    categories = list(category_service.scrape_all() or [])
    print(f"Descubrimiento de categorías: {time.perf_counter() - started:.2f} s")
    return categories


def _select_categories(categories: list[Any]) -> tuple[list[Any], int] | None:
    categories_by_key = {
        normalize_category_name(getattr(item, "name", "")): item
        for item in categories
    }
    selected = []
    selected_keys = set()
    total_expected = 0

    for target_name in TARGET_CATEGORIES:
        category = categories_by_key.get(normalize_category_name(target_name))
        if category is None:
            names = ", ".join(
                str(getattr(item, "name", "")) for item in categories
            )
            print(f"ERROR: categoría requerida no encontrada: {target_name}")
            print(f"Categorías detectadas: {names or '(ninguna)'}")
            return None

        expected_count = max(int(getattr(category, "expected_count", 0) or 0), 0)
        print(
            f"Categoría requerida: {category.name} | "
            f"productos esperados: {expected_count}"
        )
        if expected_count > MAX_EXPECTED_PER_CATEGORY:
            print(
                "CANCELADO: la categoría supera el límite de seguridad "
                f"({MAX_EXPECTED_PER_CATEGORY} productos): {category.name}"
            )
            return None

        selected.append(category)
        selected_keys.add(normalize_category_name(category.name))
        total_expected += expected_count

    if total_expected <= 0:
        print("CANCELADO: el recuento esperado no es positivo.")
        return None
    if total_expected > MAX_TOTAL_EXPECTED_PRODUCTS:
        print(
            "CANCELADO: las categorías requeridas superan el límite total "
            f"({MAX_TOTAL_EXPECTED_PRODUCTS} productos)."
        )
        return None

    optional_added = 0
    for category in categories:
        key = normalize_category_name(getattr(category, "name", ""))
        if key in selected_keys:
            continue
        expected_count = max(int(getattr(category, "expected_count", 0) or 0), 0)
        if expected_count <= 0 or expected_count > MAX_EXPECTED_PER_CATEGORY:
            continue
        if total_expected + expected_count > MAX_TOTAL_EXPECTED_PRODUCTS:
            continue
        selected.append(category)
        selected_keys.add(key)
        total_expected += expected_count
        optional_added += 1
        print(
            f"Categoría adicional incluida: {category.name} | "
            f"productos esperados: {expected_count}"
        )

    print(f"Categorías seleccionadas: {len(selected)}")
    print(f"Categorías adicionales incluidas: {optional_added}")
    print(f"Total esperado: {total_expected}")
    return selected, total_expected


def _get_browser(runner: Any) -> Any | None:
    scraping_service = getattr(runner, "scraping_service", None)
    browser_getter = getattr(scraping_service, "_browser", None)
    browser = browser_getter() if callable(browser_getter) else None
    if browser is None:
        print("ERROR: no se pudo localizar el navegador del scraping.")
        return None
    return browser


def _print_result(result: Any, log_offset: int) -> int:
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

    _print_timing_metrics(log_offset)
    success = getattr(result, "success", None)
    if callable(success):
        return 0 if success() and not errors else 1
    return 0 if not errors else 1


def _print_timing_metrics(log_offset: int) -> None:
    if not TIMING_LOG.exists():
        return

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
    if not metrics:
        return

    print("Métricas de esta ejecución:")
    for line in metrics:
        print(line)


def main() -> int:
    controller = ScrapingController()
    try:
        runner = controller.session.runner
        category_service = getattr(runner, "category_service", None)
        if category_service is None:
            print("ERROR: el runner no expone category_service.")
            return 2

        categories = _discover_categories(category_service)
        selection = _select_categories(categories)
        if selection is None:
            return 2
        selected_categories, _total_expected = selection

        browser = _get_browser(runner)
        if browser is None:
            return 2

        # Force network revalidation during this bounded directed run.
        browser._force_source_page_revalidation = True

        log_offset = TIMING_LOG.stat().st_size if TIMING_LOG.exists() else 0
        sync_started = time.perf_counter()
        result = controller.run_scraping(categories=selected_categories)
        print(
            "Duración de sincronización: "
            f"{time.perf_counter() - sync_started:.2f} s"
        )
        return _print_result(result, log_offset)
    finally:
        controller.close()


if __name__ == "__main__":
    raise SystemExit(main())
