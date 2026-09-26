from __future__ import annotations

import argparse
import shutil
import sqlite3
from pathlib import Path


EXPECTED_CATEGORIES = 24
EXPECTED_OCCURRENCES = 523
EXPECTED_PRODUCTS = 519
EXPECTED_MULTI_CATEGORY = 4
EXPECTED_RELATIONS = 523
EXPECTED_DUPLICATE_OCCURRENCES = 4


def _integrity_check(path: Path) -> None:
    with sqlite3.connect(path) as connection:
        row = connection.execute("PRAGMA integrity_check").fetchone()
    result = str(row[0]).strip().lower() if row else ""
    if result != "ok":
        raise RuntimeError(
            f"La base no supera PRAGMA integrity_check: {result or 'sin resultado'}"
        )


def _validate_database(path: Path) -> None:
    if not path.is_file():
        raise FileNotFoundError(path)

    _integrity_check(path)

    with sqlite3.connect(path) as connection:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        required = {
            "products",
            "categories",
            "product_categories",
            "scraping_runs",
            "scraping_history",
            "scraping_product_occurrences",
        }
        missing = sorted(required - tables)
        if missing:
            raise RuntimeError(
                "La base de release no contiene las tablas requeridas: "
                + ", ".join(missing)
            )

        products = connection.execute(
            "SELECT COUNT(*) FROM products"
        ).fetchone()[0]
        categories = connection.execute(
            "SELECT COUNT(*) FROM categories"
        ).fetchone()[0]
        relations = connection.execute(
            "SELECT COUNT(*) FROM product_categories"
        ).fetchone()[0]

        run = connection.execute(
            """
            SELECT
                categories_requested,
                expected_category_occurrences,
                actual_category_occurrences,
                products_found,
                products_unique,
                products_multiple_categories,
                duplicate_occurrences,
                coverage_complete,
                coverage_gap,
                error_count
            FROM scraping_runs
            WHERE mode='full' AND status='SUCCESS'
            ORDER BY id DESC
            LIMIT 1
            """
        ).fetchone()

        if (
            products != EXPECTED_PRODUCTS
            or categories != EXPECTED_CATEGORIES
            or relations != EXPECTED_RELATIONS
        ):
            raise RuntimeError(
                "La base de release no coincide con el catálogo validado: "
                f"products={products}, categories={categories}, relations={relations}; "
                f"esperado={EXPECTED_PRODUCTS}/{EXPECTED_CATEGORIES}/{EXPECTED_RELATIONS}."
            )

        if run is None:
            raise RuntimeError("No existe una ejecución FULL SUCCESS para la semilla.")

        (
            categories_requested,
            expected_occurrences,
            actual_occurrences,
            products_found,
            products_unique,
            products_multiple_category,
            duplicate_occurrences,
            coverage_complete,
            coverage_gap,
            error_count,
        ) = run

        actual = (
            categories_requested,
            expected_occurrences,
            actual_occurrences,
            products_found,
            products_unique,
            products_multiple_category,
            duplicate_occurrences,
            coverage_complete,
            coverage_gap,
            error_count,
        )
        expected = (
            EXPECTED_CATEGORIES,
            EXPECTED_OCCURRENCES,
            EXPECTED_OCCURRENCES,
            EXPECTED_OCCURRENCES,
            EXPECTED_PRODUCTS,
            EXPECTED_MULTI_CATEGORY,
            EXPECTED_DUPLICATE_OCCURRENCES,
            1,
            0,
            0,
        )

        if actual != expected:
            raise RuntimeError(
                "La última ejecución FULL SUCCESS no coincide con la referencia "
                f"24/523/519/4: actual={actual}, esperado={expected}."
            )

        image_paths = [
            str(row[0] or "").strip()
            for row in connection.execute(
                """
                SELECT image_path
                FROM products
                WHERE image_path IS NOT NULL AND TRIM(image_path) <> ''
                """
            )
        ]

    project_root = path.resolve().parent.parent
    missing_images = []
    for image_path in image_paths:
        candidate = Path(image_path)
        if not candidate.is_absolute():
            candidate = project_root / candidate
        if not candidate.is_file():
            missing_images.append(image_path)

    if missing_images:
        sample = ", ".join(missing_images[:5])
        suffix = "..." if len(missing_images) > 5 else ""
        raise RuntimeError(
            f"Faltan {len(missing_images)} imágenes referenciadas por la base: "
            f"{sample}{suffix}"
        )

    print(
        "Semilla validada: "
        f"{EXPECTED_OCCURRENCES} apariciones / "
        f"{EXPECTED_PRODUCTS} únicos / "
        f"{EXPECTED_DUPLICATE_OCCURRENCES} duplicados / "
        f"{EXPECTED_CATEGORIES} categorías / "
        f"{EXPECTED_RELATIONS} relaciones."
    )
    print(f"Imágenes referenciadas válidas: {len(image_paths)}")


def _backup_database(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(destination.name + ".tmp")
    temporary.unlink(missing_ok=True)

    try:
        with (
            sqlite3.connect(source) as source_connection,
            sqlite3.connect(temporary) as destination_connection,
        ):
            source_connection.backup(destination_connection)
            destination_connection.commit()

        _integrity_check(temporary)
        temporary.replace(destination)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def prepare_seed(
    source_database: Path,
    source_images: Path,
    output: Path,
) -> None:
    _validate_database(source_database)

    if not source_images.is_dir():
        raise FileNotFoundError(source_images)

    if output.exists():
        shutil.rmtree(output)

    seed_database = output / "database" / "catalog.db"
    seed_images = output / "data" / "images"

    _backup_database(source_database, seed_database)
    shutil.copytree(source_images, seed_images)

    print(f"Base semilla: {seed_database}")
    print(f"Imágenes semilla: {seed_images}")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Prepara la semilla validada para el bundle Windows."
    )
    parser.add_argument(
        "--database",
        type=Path,
        default=Path("database/catalog.db"),
    )
    parser.add_argument(
        "--images",
        type=Path,
        default=Path("data/images"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("build/Windows/seed"),
    )
    return parser


def main() -> None:
    args = _build_parser().parse_args()
    prepare_seed(args.database, args.images, args.output)


if __name__ == "__main__":
    main()
