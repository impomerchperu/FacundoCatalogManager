from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Imports follow the direct-execution sys.path bootstrap.
from config.runtime_paths import DATABASE_PATH
from config.scraping_config import (
    MAX_RETRIES,
    REQUEST_TIMEOUT,
    SCRAPING_CATEGORY_PAGE_WORKERS,
    SCRAPING_CATEGORY_WORKERS,
    SCRAPING_HTTP_WORKERS,
    SCRAPING_JSF_HTTP_CONCURRENCY,
    SCRAPING_JSF_PAGE_WORKERS,
    SCRAPING_MAX_WORKERS,
    STORE_URL,
)
from scrapers.browser import Browser
from scrapers.collectors.product_collection_scraper import ProductCollectionScraper
from scrapers.collectors.resilient_category_scraper import (
    ResilientCategoryScraper,
)
from scrapers.extractors.category_extractor import CategoryExtractor
from scrapers.extractors.category_product_extractor import (
    CategoryProductExtractor,
)
from scrapers.extractors.product_card_extractor import ProductCardExtractor
from scrapers.extractors.product_extractor import ProductExtractor
from services.scraping.category_name_normalizer import (
    normalize_category_name,
    split_category_names,
)
from services.scraping.category_service import CategoryService

EXPECTED_CATEGORIES = 24


def _normalize_code(value: object) -> str:
    return str(value or "").strip().upper()


def _resolve_catalog_file(database_path: Path, raw_path: object) -> Path:
    """Resolve relative image paths from the root containing the selected DB."""
    value = str(raw_path or "").strip()
    if not value:
        return Path()
    candidate = Path(value)
    if candidate.is_absolute():
        return candidate
    data_root = database_path.resolve().parent.parent
    return data_root / candidate


def _read_product_schema(
    connection: sqlite3.Connection,
) -> tuple[set[str], set[str], list[sqlite3.Row]]:
    """Inspect product-table schema and read only columns that exist."""
    tables = {
        str(row["name"])
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    if "products" not in tables:
        raise sqlite3.OperationalError("no existe la tabla products")

    product_columns = {
        str(row["name"])
        for row in connection.execute("PRAGMA table_info(products)").fetchall()
    }
    missing_required = {"code", "name"} - product_columns
    if missing_required:
        raise sqlite3.OperationalError(
            "la tabla products no contiene las columnas requeridas: "
            + ", ".join(sorted(missing_required))
        )

    selected_columns = ["code", "name"]
    selected_columns.extend(
        column
        for column in ("category", "image_path", "gallery_images")
        if column in product_columns
    )
    query = (
        "SELECT "
        + ", ".join(selected_columns)
        + " FROM products ORDER BY code COLLATE NOCASE"
    )
    rows = connection.execute(query).fetchall()
    return tables, product_columns, rows



def _discover_image_schema(
    connection: sqlite3.Connection,
    tables: set[str],
) -> list[dict[str, Any]]:
    """List image-related tables and columns without assuming a schema version."""
    tokens = (
        "image",
        "gallery",
        "photo",
        "foto",
        "media",
        "picture",
        "imagen",
        "img",
    )
    candidates: list[dict[str, Any]] = []
    for table in sorted(tables):
        if table.startswith("sqlite_"):
            continue
        quoted_table = '"' + table.replace('"', '""') + '"'
        columns = [
            str(row["name"])
            for row in connection.execute(
                f"PRAGMA table_info({quoted_table})"
            ).fetchall()
        ]
        matched = sorted(
            value
            for value in [table, *columns]
            if any(token in value.casefold() for token in tokens)
        )
        if not matched:
            continue
        row_count = int(
            connection.execute(
                f"SELECT COUNT(*) FROM {quoted_table}"
            ).fetchone()[0]
        )
        candidates.append(
            {
                "table": table,
                "columns": columns,
                "rows": row_count,
                "matched": matched,
            }
        )
    return candidates

def _read_category_relation_rows(
    connection: sqlite3.Connection,
    tables: set[str],
    product_columns: set[str],
) -> tuple[str, list[sqlite3.Row]]:
    """Use normalized relations when available, otherwise leave fallback to products.category."""
    if not {"product_categories", "categories"} <= tables or "id" not in product_columns:
        return ("products.category", []) if "category" in product_columns else ("unavailable", [])

    pc_columns = {
        str(row["name"])
        for row in connection.execute("PRAGMA table_info(product_categories)").fetchall()
    }
    category_columns = {
        str(row["name"])
        for row in connection.execute("PRAGMA table_info(categories)").fetchall()
    }
    if not {"product_id", "category_id"} <= pc_columns:
        return ("products.category", []) if "category" in product_columns else ("unavailable", [])
    if not {"id", "name"} <= category_columns:
        return ("products.category", []) if "category" in product_columns else ("unavailable", [])

    relations = connection.execute(
        """
        SELECT p.code, c.name AS category
        FROM product_categories AS pc
        JOIN products AS p ON p.id = pc.product_id
        JOIN categories AS c ON c.id = pc.category_id
        """
    ).fetchall()
    return "product_categories", relations


def _inspect_product_rows(
    database_path: Path,
    rows: list[sqlite3.Row],
    product_columns: set[str],
) -> tuple[dict[str, dict[str, str]], dict[str, Any]]:
    """Build product-code index and inspect persisted image paths when possible."""
    products: dict[str, dict[str, str]] = {}
    gallery_products = 0
    gallery_entries = 0
    missing_gallery_files = 0
    missing_primary_files = 0

    gallery_audit_available = "gallery_images" in product_columns
    primary_image_audit_available = "image_path" in product_columns

    for row in rows:
        code = _normalize_code(row["code"])
        if not code:
            continue
        products[code] = {
            "code": str(row["code"] or ""),
            "name": str(row["name"] or ""),
        }

        if primary_image_audit_available:
            primary_path = str(row["image_path"] or "").strip()
            if (
                primary_path
                and not _resolve_catalog_file(database_path, primary_path).is_file()
            ):
                missing_primary_files += 1

        if not gallery_audit_available:
            continue
        gallery = _parse_gallery(row["gallery_images"])
        valid_gallery = [
            item
            for item in gallery
            if str(item.get("image_path", item.get("path", "")) or "").strip()
        ]
        if valid_gallery:
            gallery_products += 1
        gallery_entries += len(valid_gallery)
        for item in valid_gallery:
            image_path = str(
                item.get("image_path", item.get("path", "")) or ""
            ).strip()
            if (
                image_path
                and not _resolve_catalog_file(database_path, image_path).is_file()
            ):
                missing_gallery_files += 1

    metrics = {
        "products": len(products),
        "gallery_audit_available": gallery_audit_available,
        "primary_image_audit_available": primary_image_audit_available,
        "gallery_products": gallery_products if gallery_audit_available else None,
        "gallery_entries": gallery_entries if gallery_audit_available else None,
        "missing_gallery_files": (
            missing_gallery_files if gallery_audit_available else None
        ),
        "missing_primary_files": (
            missing_primary_files if primary_image_audit_available else None
        ),
    }
    return products, metrics


def _parse_gallery(raw_value: object) -> list[dict[str, Any]]:
    try:
        parsed = json.loads(str(raw_value or "").strip() or "[]")
    except json.JSONDecodeError:
        return []
    if not isinstance(parsed, list):
        return []
    return [item for item in parsed if isinstance(item, dict)]


def _normalize_relation_rows(
    relations: list[sqlite3.Row],
) -> set[tuple[str, str]]:
    return {
        (
            _normalize_code(row["code"]),
            normalize_category_name(str(row["category"] or "")),
        )
        for row in relations
        if _normalize_code(row["code"])
        and normalize_category_name(str(row["category"] or ""))
    }


def _relations_from_product_categories(
    rows: list[sqlite3.Row],
) -> set[tuple[str, str]]:
    result: set[tuple[str, str]] = set()
    for row in rows:
        code = _normalize_code(row["code"])
        if not code:
            continue
        for category in split_category_names(str(row["category"] or "")):
            category_key = normalize_category_name(category)
            if category_key:
                result.add((code, category_key))
    return result


def _read_catalog_readonly(
    database_path: Path,
) -> tuple[dict[str, dict[str, str]], set[tuple[str, str]], dict[str, Any]]:
    """Read the existing catalog in SQLite read-only mode, including older schemas."""
    uri = f"{database_path.resolve().as_uri()}?mode=ro"
    with sqlite3.connect(uri, uri=True) as connection:
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA query_only = ON")
        tables, product_columns, rows = _read_product_schema(connection)
        image_schema_candidates = _discover_image_schema(connection, tables)
        relation_source, relation_rows = _read_category_relation_rows(
            connection,
            tables,
            product_columns,
        )

    products, image_metrics = _inspect_product_rows(
        database_path,
        rows,
        product_columns,
    )
    if relation_source == "product_categories":
        category_relations = _normalize_relation_rows(relation_rows)
    elif relation_source == "products.category":
        category_relations = _relations_from_product_categories(rows)
    else:
        category_relations = set()

    metrics = {
        **image_metrics,
        "relation_source": relation_source,
        "relations_audit_available": relation_source != "unavailable",
        "image_schema_candidates": image_schema_candidates,
    }
    return products, category_relations, metrics

def _collect_live_catalog() -> tuple[
    dict[str, dict[str, str]],
    set[tuple[str, str]],
    dict[str, Any],
]:
    browser = Browser(
        request_timeout=REQUEST_TIMEOUT,
        max_retries=MAX_RETRIES,
        http_workers=SCRAPING_HTTP_WORKERS,
    )
    browser.enable_thread_sessions()

    category_scraper = ResilientCategoryScraper(
        browser=browser,
        category_extractor=CategoryExtractor(),
        jsf_http_concurrency=SCRAPING_JSF_HTTP_CONCURRENCY,
        jsf_page_workers=SCRAPING_JSF_PAGE_WORKERS,
    )
    category_service = CategoryService(category_scraper, STORE_URL)
    collection = ProductCollectionScraper(
        category_scraper,
        ProductCardExtractor(),
        CategoryProductExtractor(),
        ProductExtractor(),
        max_workers=SCRAPING_MAX_WORKERS,
        category_page_workers=SCRAPING_CATEGORY_PAGE_WORKERS,
    )

    try:
        categories = list(category_service.scrape_all() or [])
        if len(categories) != EXPECTED_CATEGORIES:
            raise RuntimeError(
                f"Se esperaban {EXPECTED_CATEGORIES} categorías; "
                f"se encontraron {len(categories)}."
            )

        collected_by_index: list[list[Any]] = [[] for _ in categories]
        category_workers = min(SCRAPING_CATEGORY_WORKERS, len(categories))
        with ThreadPoolExecutor(max_workers=category_workers) as executor:
            futures = {
                executor.submit(collection.collect_category, category): index
                for index, category in enumerate(categories)
            }
            for future in as_completed(futures):
                collected_by_index[futures[future]] = future.result()

        expected_by_category = [
            max(int(getattr(category, "expected_count", 0) or 0), 0)
            for category in categories
        ]
        collected_by_category = [len(items) for items in collected_by_index]
        expected_occurrences = sum(expected_by_category)
        collected_occurrences = sum(collected_by_category)
        listing_gaps = [
            (
                str(getattr(categories[index], "name", "") or ""),
                expected_by_category[index],
                collected_by_category[index],
            )
            for index in range(len(categories))
            if expected_by_category[index] != collected_by_category[index]
        ]
        if listing_gaps:
            metrics = {
                "categories": len(categories),
                "expected_occurrences": expected_occurrences,
                "collected_occurrences": collected_occurrences,
                "enriched_occurrences": 0,
                "missing_codes": 0,
                "category_listing_gaps": listing_gaps,
                "http": browser.get_http_metrics(),
            }
            return {}, set(), metrics

        enriched_by_index: list[list[Any] | None] = [None] * len(categories)
        with ThreadPoolExecutor(max_workers=category_workers) as executor:
            futures = {
                executor.submit(
                    collection.enrich_category_products,
                    collected_by_index[index],
                    str(getattr(category, "name", "") or ""),
                ): index
                for index, category in enumerate(categories)
            }
            for future in as_completed(futures):
                enriched_by_index[futures[future]] = future.result()

        live_products: dict[str, dict[str, str]] = {}
        live_relations: set[tuple[str, str]] = set()
        occurrences_found = 0
        missing_codes: list[str] = []
        enrichment_gaps: list[tuple[str, int, int]] = []
        multi_categories: dict[str, set[str]] = defaultdict(set)

        for index, enriched in enumerate(enriched_by_index):
            items = list(enriched or [])
            occurrences_found += len(items)
            expected = expected_by_category[index]
            if len(items) != expected:
                enrichment_gaps.append(
                    (
                        str(getattr(categories[index], "name", "") or ""),
                        expected,
                        len(items),
                    )
                )
            category_name = str(getattr(categories[index], "name", "") or "")
            category_key = normalize_category_name(category_name)
            for product in items:
                code = _normalize_code(getattr(product, "code", ""))
                if not code:
                    missing_codes.append(
                        str(getattr(product, "url", "") or "(sin código)")
                    )
                    continue
                live_products[code] = {
                    "code": str(getattr(product, "code", "") or ""),
                    "name": str(getattr(product, "name", "") or ""),
                }
                if category_key:
                    live_relations.add((code, category_key))
                    multi_categories[code].add(category_key)

        http_metrics = browser.get_http_metrics()
        metrics = {
            "categories": len(categories),
            "expected_occurrences": expected_occurrences,
            "collected_occurrences": collected_occurrences,
            "enriched_occurrences": occurrences_found,
            "unique_codes": len(live_products),
            "multi_category_products": sum(
                len(values) > 1 for values in multi_categories.values()
            ),
            "missing_codes": len(missing_codes),
            "missing_code_urls": missing_codes,
            "category_listing_gaps": listing_gaps,
            "category_enrichment_gaps": enrichment_gaps,
            "http": http_metrics,
        }
        return live_products, live_relations, metrics
    finally:
        collection.close()


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Compara el catálogo del sitio con la base local en modo solo lectura. "
            "No aplica cambios ni sincroniza productos."
        )
    )
    parser.add_argument(
        "--database",
        type=Path,
        default=DATABASE_PATH,
        help=f"SQLite existente a leer (predeterminado: {DATABASE_PATH}).",
    )
    return parser


def main() -> int:  # noqa: PLR0912
    args = _build_parser().parse_args()
    database_path = args.database.expanduser().resolve()
    if not database_path.is_file():
        print(f"ERROR: no existe la base indicada: {database_path}")
        print("No se ha ejecutado la extracción del sitio y no se modificó nada.")
        return 2

    print("AUDITORÍA LIVE VS CATÁLOGO LOCAL — SOLO LECTURA")
    print(f"Base auditada: {database_path}")
    print("Actualización de base de datos: DESHABILITADA")
    try:
        live_products, live_relations, live_metrics = _collect_live_catalog()
    except Exception as error:  # noqa: BLE001
        print(f"ERROR al extraer el sitio: {type(error).__name__}: {error}")
        print("No se aplicaron cambios a la base de datos.")
        return 2

    print(f"Categorías live: {live_metrics['categories']}")
    print(
        "Apariciones esperadas / tarjetas: "
        f"{live_metrics['expected_occurrences']} / "
        f"{live_metrics['collected_occurrences']}"
    )
    print(f"Apariciones enriquecidas: {live_metrics['enriched_occurrences']}")
    if live_metrics.get("category_listing_gaps"):
        print("ABORTADO: la cobertura de tarjetas no coincide con las cantidades publicadas.")
        for category, expected, found in live_metrics["category_listing_gaps"]:
            print(f"  BRECHA TARJETAS | {category} | esperado={expected} | encontrado={found}")
        print("No se comparan códigos para evitar falsos productos ausentes.")
        return 2
    if live_metrics.get("category_enrichment_gaps"):
        print("ABORTADO: la cantidad enriquecida no coincide con las apariciones esperadas.")
        for category, expected, found in live_metrics["category_enrichment_gaps"]:
            print(f"  BRECHA DETALLE | {category} | esperado={expected} | encontrado={found}")
        print("No se comparan códigos para evitar falsos productos ausentes.")
        return 2
    if live_metrics["missing_codes"]:
        print(f"ABORTADO: hay {live_metrics['missing_codes']} apariciones sin código.")
        for url in live_metrics["missing_code_urls"][:20]:
            print(f"  SIN CÓDIGO | {url}")
        print("No se comparan códigos para evitar falsos productos ausentes.")
        return 2

    http = live_metrics["http"]
    print(
        "HTTP: "
        f"requests={http.get('http_requests', 0)} "
        f"retries={http.get('http_retries', 0)} "
        f"errors={http.get('http_errors', 0)} "
        f"terminal={http.get('http_terminal_errors', 0)}"
    )

    http_terminal_errors = int(http.get("http_terminal_errors", 0) or 0)
    http_errors = int(http.get("http_errors", 0) or 0)
    if http_terminal_errors or http_errors:
        print(
            "ABORTADO: la extracción registró errores HTTP; "
            "no es seguro comparar posibles productos ausentes."
        )
        return 2

    try:
        database_products, database_relations, database_metrics = (
            _read_catalog_readonly(database_path)
        )
    except (OSError, sqlite3.Error, ValueError) as error:
        print(f"ERROR al leer la base en modo solo lectura: {error}")
        print("No se aplicaron cambios a la base de datos.")
        return 2

    live_codes = set(live_products)
    database_codes = set(database_products)
    missing_live = sorted(database_codes - live_codes)
    new_live = sorted(live_codes - database_codes)
    print("=" * 80)
    print("RESUMEN DE CÓDIGOS")
    print(f"Productos únicos live: {len(live_codes)}")
    print(f"Productos únicos en DB: {len(database_codes)}")
    print(f"Códigos presentes en DB pero ausentes del sitio: {len(missing_live)}")
    for code in missing_live:
        item = database_products[code]
        print(f"  AUSENTE EN LIVE | {item['code']} | {item['name']}")
    print(f"Códigos del sitio que no están en DB: {len(new_live)}")
    for code in new_live:
        item = live_products[code]
        print(f"  NUEVO EN LIVE | {item['code']} | {item['name']}")

    print("=" * 80)
    print("RESUMEN DE RELACIONES CATEGORÍA-PRODUCTO")
    if database_metrics["relations_audit_available"]:
        db_only_relations = sorted(database_relations - live_relations)
        live_only_relations = sorted(live_relations - database_relations)
        print(f"Fuente en DB: {database_metrics['relation_source']}")
        print(f"Relaciones live: {len(live_relations)}")
        print(f"Relaciones en DB: {len(database_relations)}")
        print(f"Relaciones existentes en DB que no están en live: {len(db_only_relations)}")
        for code, category in db_only_relations:
            print(f"  RELACIÓN AUSENTE EN LIVE | {code} | {category}")
        print(f"Relaciones live ausentes de DB: {len(live_only_relations)}")
        for code, category in live_only_relations:
            item = live_products.get(code, {})
            print(
                f"  RELACIÓN NUEVA EN LIVE | {item.get('code', code)} | {category}"
            )
    else:
        print(
            "NO DISPONIBLE: la base no contiene ni las relaciones normalizadas "
            "ni la columna products.category."
        )

    print("=" * 80)
    print("ESTADO DE LAS IMÁGENES GUARDADAS")
    if database_metrics["gallery_audit_available"]:
        print(
            "Productos DB con galería registrada: "
            f"{database_metrics['gallery_products']}"
        )
        print(f"Entradas de galería registradas: {database_metrics['gallery_entries']}")
        print(
            "Archivos de galería inexistentes: "
            f"{database_metrics['missing_gallery_files']}"
        )
    else:
        print(
            "Galerías no auditables: no existe la columna "
            "products.gallery_images."
        )
        candidates = database_metrics["image_schema_candidates"]
        if candidates:
            print("Esquema relacionado con imágenes detectado (solo lectura):")
            for candidate in candidates:
                columns = ", ".join(candidate["columns"])
                matched = ", ".join(candidate["matched"])
                print(
                    f"  TABLA {candidate['table']} | filas={candidate['rows']} "
                    f"| columnas=[{columns}] | coincidencias=[{matched}]"
                )
        else:
            print("No se detectaron tablas/columnas relacionadas con imágenes.")
    if database_metrics["primary_image_audit_available"]:
        print(
            "Imágenes principales con ruta inexistente: "
            f"{database_metrics['missing_primary_files']}"
        )
    else:
        print(
            "Imágenes principales no auditables: falta products.image_path."
        )
    print("=" * 80)
    print("SOLO DIAGNÓSTICO: no se ha escrito ni eliminado ningún dato.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
