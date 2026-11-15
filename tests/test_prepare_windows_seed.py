import sqlite3
from pathlib import Path

import pytest

from tools import prepare_windows_seed
from tools.prepare_windows_seed import prepare_seed

TEST_CATEGORIES = 24
TEST_OCCURRENCES = 521
TEST_PRODUCTS = 518
TEST_MULTI_CATEGORY = 3
TEST_RELATIONS = 521
TEST_DUPLICATE_OCCURRENCES = 3


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
            CREATE TABLE scraping_product_occurrences (
                id INTEGER PRIMARY KEY,
                run_id INTEGER,
                category_id INTEGER,
                product_id INTEGER,
                code TEXT,
                product_url TEXT
            );
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
            [(index,) for index in range(1, TEST_CATEGORIES + 1)],
        )
        connection.executemany(
            "INSERT INTO products (id, image_path) VALUES (?, ?)",
            [
                (index, image_path)
                for index in range(1, TEST_PRODUCTS + 1)
            ],
        )
        relationships = [
            (product_id, (product_id - 1) % TEST_CATEGORIES + 1)
            for product_id in range(1, TEST_PRODUCTS + 1)
        ]
        relationships.extend(
            (product_id, product_id % TEST_CATEGORIES + 1)
            for product_id in range(1, TEST_MULTI_CATEGORY + 1)
        )
        assert len(relationships) == TEST_RELATIONS
        connection.executemany(
            "INSERT INTO product_categories (product_id, category_id) VALUES (?, ?)",
            relationships,
        )
        connection.executemany(
            """
            INSERT INTO scraping_product_occurrences (
                run_id, category_id, product_id, code, product_url
            ) VALUES (1, ?, ?, ?, ?)
            """,
            [
                (
                    category_id,
                    product_id,
                    f"P-{product_id}",
                    f"https://example.test/P-{product_id}",
                )
                for product_id, category_id in relationships
            ],
        )
        run_values = {
            "categories_requested": TEST_CATEGORIES,
            "expected_category_occurrences": TEST_OCCURRENCES,
            "actual_category_occurrences": TEST_OCCURRENCES,
            "products_found": TEST_OCCURRENCES,
            "products_unique": TEST_PRODUCTS,
            "products_multiple_categories": TEST_MULTI_CATEGORY,
            "duplicate_occurrences": TEST_DUPLICATE_OCCURRENCES,
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
    source_bytes = db.read_bytes()
    output = tmp_path / "build" / "Windows" / "seed"

    prepare_seed(db, root / "data" / "images", output)

    assert (output / "database" / "catalog.db").is_file()
    assert (output / "data" / "images" / "products" / "sample.jpg").is_file()
    assert db.read_bytes() == source_bytes

    with sqlite3.connect(output / "database" / "catalog.db") as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM products"
        ).fetchone()[0] == TEST_PRODUCTS



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
        connection.execute("DELETE FROM products WHERE id=?", (TEST_PRODUCTS,))
        connection.commit()

    with pytest.raises(RuntimeError, match="no son consistentes"):
        prepare_seed(db, root / "data" / "images", root / "build" / "seed")


def test_prepare_seed_rejects_output_that_contains_source_data(tmp_path):
    root = tmp_path
    db_dir = root / "database"
    images = root / "data" / "images"
    db_dir.mkdir(parents=True)
    (images / "products").mkdir(parents=True)
    image = images / "products" / "sample.jpg"
    image.write_bytes(b"image")

    db = db_dir / "catalog.db"
    _create_valid_database(db, "data/images/products/sample.jpg")

    with pytest.raises(ValueError, match="no puede solaparse"):
        prepare_seed(db, images, root)

    assert db.is_file()
    assert image.is_file()


def test_prepare_seed_resolves_images_from_the_supplied_image_root(tmp_path):
    root = tmp_path
    db_dir = root / "database"
    images = root / "assets" / "data" / "images" / "products"
    db_dir.mkdir(parents=True)
    images.mkdir(parents=True)
    image = images / "sample.jpg"
    image.write_bytes(b"image")

    db = db_dir / "catalog.db"
    _create_valid_database(db, "data/images/products/sample.jpg")
    output = root / "seed"

    prepare_seed(db, images.parent, output)

    assert (output / "data" / "images" / "products" / "sample.jpg").is_file()


def test_prepare_seed_rejects_database_with_pending_wal(tmp_path, monkeypatch):
    root = tmp_path
    db_dir = root / "database"
    images = root / "data" / "images" / "products"
    db_dir.mkdir(parents=True)
    images.mkdir(parents=True)
    (images / "sample.jpg").write_bytes(b"image")

    db = db_dir / "catalog.db"
    _create_valid_database(db, "data/images/products/sample.jpg")
    Path(f"{db}-wal").write_bytes(b"pending transaction")
    output = root / "seed"

    connect = sqlite3.connect

    def fail_normal_readonly_open(database_uri, *args, **kwargs):
        if "immutable=1" not in str(database_uri):
            error = sqlite3.OperationalError("unable to open database file")
            error.sqlite_errorcode = sqlite3.SQLITE_CANTOPEN
            raise error
        return connect(database_uri, *args, **kwargs)

    monkeypatch.setattr(prepare_windows_seed.sqlite3, "connect", fail_normal_readonly_open)

    with pytest.raises(RuntimeError, match="transacción SQLite pendiente"):
        prepare_seed(db, root / "data" / "images", output)

    assert not output.exists()


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

    with pytest.raises(RuntimeError, match="no son consistentes"):
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
