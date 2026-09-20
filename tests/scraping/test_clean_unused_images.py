from __future__ import annotations

import sqlite3
from pathlib import Path

from tools.clean_unused_images import (
    clean_unused_images,
    find_unused_images,
)


def _create_products_db(path: Path) -> None:
    connection = sqlite3.connect(path)
    connection.execute(
        """
        CREATE TABLE products (
            id INTEGER PRIMARY KEY,
            code TEXT,
            image_path TEXT
        )
        """
    )
    connection.commit()
    connection.close()


def _insert_product(path: Path, image_path: str) -> None:
    connection = sqlite3.connect(path)
    connection.execute(
        "INSERT INTO products (code, image_path) VALUES (?, ?)",
        ("P001", image_path),
    )
    connection.commit()
    connection.close()


def test_find_unused_images_uses_products_as_allowlist(tmp_path: Path):
    project = tmp_path
    root = project / "data" / "images"
    products = root / "products"
    products.mkdir(parents=True)

    active = products / "P001.webp"
    legacy = root / "old.webp"
    active.write_bytes(b"active")
    legacy.write_bytes(b"legacy")

    db = project / "database" / "catalog.db"
    db.parent.mkdir()
    _create_products_db(db)
    _insert_product(db, "data/images/products/P001.webp")

    candidates = find_unused_images(
        project_root=project,
        db_path=db,
        roots=[root],
    )

    assert [item["relative"] for item in candidates] == [
        "data/images/old.webp"
    ]


def test_clean_unused_images_can_delete_only_unreferenced_files(
    tmp_path: Path,
):
    project = tmp_path
    root = project / "data" / "images"
    products = root / "products"
    resources = project / "resources" / "images"
    products.mkdir(parents=True)
    resources.mkdir(parents=True)

    active = products / "P001.webp"
    legacy = root / "old.webp"
    historical = resources / "P002.jpg"
    active.write_bytes(b"active")
    legacy.write_bytes(b"legacy")
    historical.write_bytes(b"historical")

    db = project / "database" / "catalog.db"
    db.parent.mkdir()
    _create_products_db(db)
    _insert_product(db, "data/images/products/P001.webp")

    deleted = clean_unused_images(
        project_root=project,
        db_path=db,
        roots=["data/images", "resources/images"],
        delete=True,
    )

    assert {
        item["relative"] for item in deleted
    } == {
        "data/images/old.webp",
        "resources/images/P002.jpg",
    }
    assert active.is_file()
    assert not legacy.exists()
    assert not historical.exists()


def test_clean_unused_images_does_not_delete_missing_or_outside_files(
    tmp_path: Path,
):
    project = tmp_path
    root = project / "data" / "images"
    root.mkdir(parents=True)

    db = project / "database" / "catalog.db"
    db.parent.mkdir()
    _create_products_db(db)

    missing_roots = clean_unused_images(
        project_root=project,
        db_path=db,
        roots=["data/images", "not-present"],
        delete=True,
    )

    assert missing_roots == []
