import sqlite3
from pathlib import Path

import pytest

from tools.prepare_windows_seed import (
    EXPECTED_CATEGORIES,
    EXPECTED_DUPLICATE_OCCURRENCES,
    EXPECTED_MULTI_CATEGORY,
    EXPECTED_OCCURRENCES,
    EXPECTED_PRODUCTS,
    EXPECTED_RELATIONS,
    prepare_seed,
)


def _create_valid_database(
    path: Path,
    image_path: str,
    *,
    run_overrides: dict[str, int] | None = None,
) -> None:
    with sqlite3.connect(path) as connection:
        connection.executescript(
            """
            CREATE TABLE products (
                id INTEGER PRIMARY KEY,
                image_path TEXT
            );
            CREATE TABLE categories (id INTEGER PRIMARY KEY);
            CREATE TABLE product_categories (product_id INTEGER, category_id INTEGER);
            CREATE TABLE scraping_history (id INTEGER PRIMARY KEY);
            CREATE TABLE scraping_product_occurrences (id INTEGER PRIMARY KEY);
            CREATE TABLE scraping_runs (
                id INTEGER PRIMARY KEY,
                mode TEXT,
                status TEXT,
                categories_requested INTEGER,
                expected_category_occurrences INTEGER,
                actual_category_occurrences INTEGER,
                products_found INTEGER,
                products_unique INTEGER,
                products_multiple_categories INTEGER,
                duplicate_occurrences INTEGER,
                coverage_complete INTEGER,
                coverage_gap INTEGER,
                error_count INTEGER
            );
            """
        )
        connection.executemany(
            "INSERT INTO categories (id) VALUES (?)",
            [(index,) for index in range(EXPECTED_CATEGORIES)],
        )
        connection.executemany(
            "INSERT INTO products (id, image_path) VALUES (?, ?)",
            [
                (index, image_path)
                for index in range(1, EXPECTED_PRODUCTS + 1)
            ],
        )
        connection.executemany(
            "INSERT INTO product_categories (product_id, category_id) VALUES (?, ?)",
            [
                (
                    index % EXPECTED_PRODUCTS + 1,
                    index % EXPECTED_CATEGORIES,
                )
                for index in range(EXPECTED_RELATIONS)
            ],
        )
        run_values = {
            "categories_requested": EXPECTED_CATEGORIES,
            "expected_category_occurrences": EXPECTED_OCCURRENCES,
            "actual_category_occurrences": EXPECTED_OCCURRENCES,
            "products_found": EXPECTED_OCCURRENCES,
            "products_unique": EXPECTED_PRODUCTS,
            "products_multiple_categories": EXPECTED_MULTI_CATEGORY,
            "duplicate_occurrences": EXPECTED_DUPLICATE_OCCURRENCES,
            "coverage_complete": 1,
            "coverage_gap": 0,
            "error_count": 0,
        }
        if run_overrides:
            run_values.update(run_overrides)

        connection.execute(
            """
            INSERT INTO scraping_runs (
                id, mode, status, categories_requested,
                expected_category_occurrences, actual_category_occurrences,
                products_found, products_unique, products_multiple_categories,
                duplicate_occurrences, coverage_complete, coverage_gap, error_count
            ) VALUES (1, 'full', 'SUCCESS', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            tuple(
                run_values[key]
                for key in (
                    "categories_requested",
                    "expected_category_occurrences",
                    "actual_category_occurrences",
                    "products_found",
                    "products_unique",
                    "products_multiple_categories",
                    "duplicate_occurrences",
                    "coverage_complete",
                    "coverage_gap",
                    "error_count",
                )
            ),
        )


def test_prepare_seed_rejects_missing_image(tmp_path):
    db = tmp_path / "catalog.db"
    images = tmp_path / "images"
    output = tmp_path / "seed"
    images.mkdir()
    _create_valid_database(db, "data/images/products/missing.jpg")

    with pytest.raises(RuntimeError, match="Faltan"):
        prepare_seed(db, images, output)


def test_prepare_seed_creates_seed_with_valid_database(tmp_path):
    root = tmp_path
    db_dir = root / "database"
    images = root / "data" / "images" / "products"
    db_dir.mkdir(parents=True)
    images.mkdir(parents=True)

    image = root / "data" / "images" / "products" / "sample.jpg"
    image.write_bytes(b"image")

    db = db_dir / "catalog.db"
    _create_valid_database(db, "data/images/products/sample.jpg")
    output = tmp_path / "build" / "Windows" / "seed"

    prepare_seed(db, root / "data" / "images", output)

    assert (output / "database" / "catalog.db").is_file()
    assert (output / "data" / "images" / "products" / "sample.jpg").is_file()

    with sqlite3.connect(output / "database" / "catalog.db") as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM products"
        ).fetchone()[0] == EXPECTED_PRODUCTS



def test_prepare_seed_rejects_catalog_count_mismatch(tmp_path):
    root = tmp_path
    db_dir = root / "database"
    images = root / "data" / "images" / "products"
    db_dir.mkdir(parents=True)
    images.mkdir(parents=True)
    image = images / "sample.jpg"
    image.write_bytes(b"image")

    db = db_dir / "catalog.db"
    _create_valid_database(db, "data/images/products/sample.jpg")
    with sqlite3.connect(db) as connection:
        connection.execute("DELETE FROM products WHERE id=?", (EXPECTED_PRODUCTS,))
        connection.commit()

    with pytest.raises(RuntimeError, match="catálogo validado"):
        prepare_seed(db, root / "data" / "images", root / "build" / "seed")


def test_prepare_seed_rejects_invalid_full_run(tmp_path):
    root = tmp_path
    db_dir = root / "database"
    images = root / "data" / "images" / "products"
    db_dir.mkdir(parents=True)
    images.mkdir(parents=True)
    image = images / "sample.jpg"
    image.write_bytes(b"image")

    db = db_dir / "catalog.db"
    _create_valid_database(
        db,
        "data/images/products/sample.jpg",
        run_overrides={"coverage_gap": 1},
    )

    with pytest.raises(RuntimeError, match="referencia 24/523/519/4"):
        prepare_seed(db, root / "data" / "images", root / "build" / "seed")


def test_prepare_seed_rejects_missing_full_success(tmp_path):
    root = tmp_path
    db_dir = root / "database"
    images = root / "data" / "images" / "products"
    db_dir.mkdir(parents=True)
    images.mkdir(parents=True)
    image = images / "sample.jpg"
    image.write_bytes(b"image")

    db = db_dir / "catalog.db"
    _create_valid_database(
        db,
        "data/images/products/sample.jpg",
        run_overrides={"coverage_complete": 0},
    )
    with sqlite3.connect(db) as connection:
        connection.execute("UPDATE scraping_runs SET status='FAILED'")
        connection.commit()

    with pytest.raises(RuntimeError, match="No existe una ejecución FULL SUCCESS"):
        prepare_seed(db, root / "data" / "images", root / "build" / "seed")
