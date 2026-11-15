from __future__ import annotations

import argparse
import shutil
import sqlite3
from contextlib import closing
from pathlib import Path


def _ensure_no_pending_transaction(path: Path) -> None:
    for suffix in ("-wal", "-journal"):
        journal = Path(f"{path}{suffix}")
        if journal.is_file() and journal.stat().st_size:
            raise RuntimeError(
                "La base tiene una transacción SQLite pendiente; cierra la aplicación "
                f"o espera a que termine antes de preparar la semilla: {journal}"
            )


def _connect_readonly(path: Path) -> sqlite3.Connection:
    """Open a read-only SQLite snapshot, preserving normal locking when possible."""
    uri = f"{path.resolve().as_uri()}?mode=ro"
    connection: sqlite3.Connection | None = None
    try:
        connection = sqlite3.connect(uri, uri=True)
        connection.execute("PRAGMA schema_version").fetchone()
    except sqlite3.OperationalError as error:
        if connection is not None:
            connection.close()
        if (error.sqlite_errorcode or 0) & 0xFF != sqlite3.SQLITE_CANTOPEN:
            raise
    else:
        return connection

    _ensure_no_pending_transaction(path)
    immutable_uri = f"{path.resolve().as_uri()}?mode=ro&immutable=1"
    connection = sqlite3.connect(immutable_uri, uri=True)
    try:
        connection.execute("PRAGMA schema_version").fetchone()
    except Exception:
        connection.close()
        raise
    return connection


def _integrity_check(path: Path) -> None:
    with closing(_connect_readonly(path)) as connection:
        row = connection.execute("PRAGMA integrity_check").fetchone()
    result = str(row[0]).strip().lower() if row else ""
    if result != "ok":
        raise RuntimeError(
            f"La base no supera PRAGMA integrity_check: {result or 'sin resultado'}"
        )


def _validate_database(path: Path, source_images: Path | None = None) -> None:
    if not path.is_file():
        raise FileNotFoundError(path)

    _integrity_check(path)

    with closing(_connect_readonly(path)) as connection:
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
                id,
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

        if products < 1 or categories < 1 or relations < 1:
            raise RuntimeError(
                "La base de release tiene un catálogo vacío o incompleto: "
                f"products={products}, categories={categories}, relations={relations}."
            )

        if run is None:
            raise RuntimeError("No existe una ejecución FULL SUCCESS para la semilla.")

        (
            run_id,
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

        occurrences = connection.execute(
            """
            SELECT
                COUNT(*),
                COUNT(DISTINCT code),
                COUNT(DISTINCT category_id),
                SUM(CASE WHEN TRIM(code) = '' THEN 1 ELSE 0 END)
            FROM scraping_product_occurrences
            WHERE run_id = ?
            """,
            (run_id,),
        ).fetchone()
        occurrence_count, unique_codes, occurrence_categories, missing_codes = (
            int(value or 0) for value in occurrences
        )

        multi_category_products = connection.execute(
            """
            SELECT COUNT(*)
            FROM (
                SELECT product_id
                FROM product_categories
                GROUP BY product_id
                HAVING COUNT(DISTINCT category_id) > 1
            )
            """
        ).fetchone()[0]

        consistent = (
            categories_requested == categories
            and expected_occurrences > 0
            and actual_occurrences == expected_occurrences
            and products_found == expected_occurrences
            and occurrence_count == expected_occurrences
            and occurrence_categories == categories
            and unique_codes == products_unique == products
            and products_multiple_category == multi_category_products
            and duplicate_occurrences == expected_occurrences - products_unique
            and relations == expected_occurrences
            and missing_codes == 0
            and coverage_complete == 1
            and coverage_gap == 0
            and error_count == 0
        )

        if not consistent:
            raise RuntimeError(
                "La última ejecución FULL SUCCESS y el catálogo no son consistentes: "
                f"run_id={run_id}, categorías={categories_requested}/{categories}, "
                f"apariciones={actual_occurrences}/{expected_occurrences} "
                f"(ocurrencias={occurrence_count}), únicos={unique_codes}/"
                f"{products_unique}/{products}, relaciones={relations}, "
                f"multi-categoría={multi_category_products}/"
                f"{products_multiple_category}, sin código={missing_codes}, "
                f"coverage_complete={coverage_complete}, gap={coverage_gap}, "
                f"errores={error_count}."
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

    project_root = (
        source_images.resolve().parent.parent
        if source_images is not None
        else path.resolve().parent.parent
    )
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
        "Semilla validada contra la última ejecución FULL: "
        f"{actual_occurrences} apariciones / {products_unique} únicos / "
        f"{duplicate_occurrences} duplicados / {categories} categorías / "
        f"{relations} relaciones."
    )
    print(f"Imágenes referenciadas válidas: {len(image_paths)}")


def _backup_database(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.unlink(missing_ok=True)

    try:
        with closing(_connect_readonly(source)) as source_connection:
            destination_connection = sqlite3.connect(destination)
            try:
                source_connection.backup(destination_connection)
                destination_connection.commit()
            finally:
                destination_connection.close()

        _integrity_check(destination)
    except Exception:
        destination.unlink(missing_ok=True)
        raise


def _validate_output_path(
    source_database: Path,
    source_images: Path,
    output: Path,
) -> None:
    resolved_output = output.resolve()
    for source in (source_database.resolve(), source_images.resolve()):
        if (
            resolved_output == source
            or resolved_output.is_relative_to(source)
            or source.is_relative_to(resolved_output)
        ):
            raise ValueError(
                "La carpeta de salida no puede solaparse con la base o las imágenes: "
                f"output={resolved_output}, source={source}."
            )


def prepare_seed(
    source_database: Path,
    source_images: Path,
    output: Path,
) -> None:
    _validate_output_path(source_database, source_images, output)
    if not source_images.is_dir():
        raise FileNotFoundError(source_images)

    _validate_database(source_database, source_images)

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
