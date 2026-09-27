from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from tools.prepare_windows_seed import prepare_seed


ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = ROOT / "database" / "schema.sql"


def _create_valid_database(
    path: Path,
    *,
    image_path: str | None = None,
    run_override: dict[str, int] | None = None,
) -> None:
    with sqlite3.connect(path) as connection:
        connection.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))

        categories = [
            (f"Category {index}", f"https://example.com/category/{index}")
            for index in range(24)
        ]
        connection.executemany(
            "INSERT INTO categories (name, canonical_url) VALUES (?, ?)",
            categories,
        )

        products = [
            (
                f"P{index:03d}",
                f"Product {index}",
                image_path if index == 1 else None,
            )
            for index in range(1, 520)
        ]
        connection.executemany(
            "INSERT INTO products (code, name, image_path) VALUES (?, ?, ?)",
            products,
        )

        relations = [(index, 1) for index in range(1, 520)]
        relations.extend(
            [
                (2, 2),
                (3, 3),
                (4, 4),
                (5, 5),
            ]
        )
        connection.executemany(
            "INSERT INTO product_categories (product_id, category_id) VALUES (?, ?)",
            relations,
        )

        values = {
            "categories_requested": 24,
            "expected_category_occurrences": 523,
            "actual_category_occurrences": 523,
            "products_found": 523,
            "products_unique": 519,
            "products_multiple_categories": 4,
            "duplicate_occurrences": 4,
            "coverage_complete": 1,
            "coverage_gap": 0,
            "error_count": 0,
        }
        if run_override:
            values.update(run_override)

        connection.execute(
            """
            INSERT INTO scraping_runs (
                started_at,
                finished_at,
                mode,
                status,
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
            )
            VALUES (
                '2026-09-27T10:00:00',
                '2026-09-27T10:01:00',
                'full',
                'SUCCESS',
                ?,
                ?,
                ?,
                ?,
                ?,
                ?,
                ?,
                ?,
                ?,
                ?
            )
            """,
            tuple(values[key] for key in (
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
            )),
        )
        connection.commit()


def test_prepare_seed_copies_a_validated_catalog_and_images(tmp_path: Path):
    database = tmp_path / "catalog.db"
    images = tmp_path / "images"
    output = tmp_path / "seed"
    images.mkdir()
    (images / "placeholder.png").write_bytes(b"png")

    _create_valid_database(database)

    prepare_seed(database, images, output)

    seed_database = output / "database" / "catalog.db"
    seed_image = output / "data" / "images" / "placeholder.png"

    assert seed_database.is_file()
    assert seed_image.read_bytes() == b"png"

    with sqlite3.connect(seed_database) as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM products"
        ).fetchone()[0] == 519
        assert connection.execute(
            "SELECT COUNT(*) FROM categories"
        ).fetchone()[0] == 24
        assert connection.execute(
            "SELECT COUNT(*) FROM product_categories"
        ).fetchone()[0] == 523
        assert connection.execute(
            """
            SELECT products_unique, products_multiple_categories,
                   duplicate_occurrences, coverage_complete, coverage_gap,
                   error_count
            FROM scraping_runs
            WHERE mode='full' AND status='SUCCESS'
            ORDER BY id DESC
            LIMIT 1
            """
        ).fetchone() == (519, 4, 4, 1, 0, 0)


def test_prepare_seed_rejects_catalog_count_mismatch(tmp_path: Path):
    database = tmp_path / "catalog.db"
    images = tmp_path / "images"
    output = tmp_path / "seed"
    images.mkdir()

    _create_valid_database(
        database,
        run_override={"products_unique": 518},
    )

    with pytest.raises(RuntimeError, match="catálogo validado"):
        prepare_seed(database, images, output)

    assert not output.exists()


def test_prepare_seed_rejects_invalid_full_run(tmp_path: Path):
    database = tmp_path / "catalog.db"
    images = tmp_path / "images"
    output = tmp_path / "seed"
    images.mkdir()

    _create_valid_database(
        database,
        run_override={"coverage_gap": 1},
    )

    with pytest.raises(
        RuntimeError,
        match="referencia 24/523/519/4",
    ):
        prepare_seed(database, images, output)

    assert not output.exists()


def test_prepare_seed_rejects_missing_full_success(tmp_path: Path):
    database = tmp_path / "catalog.db"
    images = tmp_path / "images"
    output = tmp_path / "seed"
    images.mkdir()

    _create_valid_database(
        database,
        run_override={"coverage_complete": 0},
    )
    with sqlite3.connect(database) as connection:
        connection.execute("UPDATE scraping_runs SET status='FAILED'")
        connection.commit()

    with pytest.raises(
        RuntimeError,
        match="No existe una ejecución FULL SUCCESS",
    ):
        prepare_seed(database, images, output)

    assert not output.exists()


def test_prepare_seed_rejects_missing_referenced_image(tmp_path: Path):
    database = tmp_path / "catalog.db"
    images = tmp_path / "images"
    output = tmp_path / "seed"
    images.mkdir()

    _create_valid_database(
        database,
        image_path="data/images/missing.png",
    )

    with pytest.raises(RuntimeError, match="Faltan 1 imágenes"):
        prepare_seed(database, images, output)

    assert not output.exists()
