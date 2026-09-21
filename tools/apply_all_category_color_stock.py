from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from factories.scraping_factory import ScrapingFactory
from repositories.product_repository import ProductRepository
from services.scraping.scraping_session import ScrapingSession
from services.scraping.category_name_normalizer import split_category_names

EXPECTED_CATEGORIES = 24


def _products_by_category(products) -> dict[str, list]:
    result: dict[str, list] = defaultdict(list)
    for product in products:
        color_stock = getattr(product, "color_stock", {}) or {}
        if not color_stock:
            continue
        for category in split_category_names(
            getattr(product, "category", "")
        ):
            category_name = str(category).strip()
            if category_name:
                result[category_name].append(product)
    return dict(result)


def main() -> int:
    runner = ScrapingFactory.create_runner()
    session = ScrapingSession(
        runner,
        history_repository=runner.history_repository,
        catalog_repository=runner.catalog_repository,
    )

    try:
        category_service = getattr(runner, "category_service", None)
        if category_service is None:
            print("VERIFICACIÓN CATEGORÍAS: ERROR - category service no disponible")
            return 1

        categories = list(category_service.scrape_all() or [])
        print("CATEGORÍAS DESCUBIERTAS:", len(categories))
        if len(categories) != EXPECTED_CATEGORIES:
            print(
                "VERIFICACIÓN CATEGORÍAS: ERROR -",
                len(categories),
                "!=",
                EXPECTED_CATEGORIES,
            )
            return 1

        # Todas las categorías se ejecutan como un sync dirigido conjunto:
        # se aplica color_stock a todas sin habilitar prune FULL.
        result = session.execute(categories)

        print("=" * 80)
        print("APLICACIÓN FULL DE STOCK POR COLOR")
        print("=" * 80)
        print("ESTADO:", result.status())
        print("CATEGORÍAS PROCESADAS:", result.categories_processed)
        print("APARICIONES ESPERADAS:", result.expected_category_occurrences)
        print("APARICIONES ENCONTRADAS:", result.products_found)
        print("PRODUCTOS ÚNICOS:", result.products_unique)
        print("CREADOS:", result.created)
        print("ACTUALIZADOS:", result.updated)
        print("SIN CAMBIOS:", result.unchanged)
        print("ELIMINADOS:", result.deleted)
        print("HISTORIAL ID:", result.history_id)
        print("ERRORES:", len(result.errors))

        if not result.success():
            if result.errors:
                print("DETALLE DE ERRORES:")
                for error in result.errors:
                    print("-", error)
            return 1

        if result.categories_processed != EXPECTED_CATEGORIES:
            print(
                "VERIFICACIÓN CATEGORÍAS: ERROR -",
                result.categories_processed,
                "!=",
                EXPECTED_CATEGORIES,
            )
            return 1

        if result.category_occurrence_gap:
            print(
                "VERIFICACIÓN COBERTURA: ERROR - gap=",
                result.category_occurrence_gap,
            )
            return 1

        color_products = [
            product
            for product in result.products
            if getattr(product, "color_stock", {}) or {}
        ]

        persisted_products = ProductRepository(
            runner.catalog_repository.db,
        ).get_all()
        persisted_by_code = {
            str(product.code).strip().upper(): product
            for product in persisted_products
            if str(getattr(product, "code", "")).strip()
        }

        mismatches: list[str] = []
        for product in color_products:
            code = str(product.code).strip().upper()
            persisted = persisted_by_code.get(code)
            if persisted is None:
                mismatches.append(f"{code}: producto no persistido")
                continue
            expected = dict(product.color_stock)
            actual = dict(getattr(persisted, "color_stock", {}) or {})
            if actual != expected:
                mismatches.append(
                    f"{code}: esperado={expected} persistido={actual}"
                )
            expected_total = sum(expected.values())
            if int(getattr(persisted, "stock", 0)) != expected_total:
                mismatches.append(
                    f"{code}: stock esperado={expected_total} "
                    f"persistido={persisted.stock}"
                )

        print("PRODUCTOS CON STOCK POR COLOR:", len(color_products))
        print("VERIFICACIONES BD:", len(color_products))
        print("INCONSISTENCIAS BD:", len(mismatches))

        by_category = _products_by_category(color_products)
        print("CATEGORÍAS CON STOCK POR COLOR:", len(by_category))
        for category_name in sorted(by_category):
            print(
                f" - {category_name}: "
                f"{len(by_category[category_name])} productos"
            )

        if len(by_category) == EXPECTED_CATEGORIES:
            print("CATEGORÍAS CON STOCK POR COLOR: 24/24")
        else:
            print(
                "CATEGORÍAS CON STOCK POR COLOR:",
                f"{len(by_category)}/{EXPECTED_CATEGORIES}",
                "(las categorías restantes pueden no publicar "
                "cantidades por color en el origen)",
            )

        if mismatches:
            print("DETALLE DE INCONSISTENCIAS:")
            for mismatch in mismatches:
                print("-", mismatch)
            return 1

        print("=" * 80)
        return 0
    finally:
        session.close()


if __name__ == "__main__":
    raise SystemExit(main())
