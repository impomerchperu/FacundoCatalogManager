from __future__ import annotations

import hashlib
import sqlite3
from pathlib import Path

from tools.audit_image_storage import audit


def _create_db(path: Path) -> None:
    connection = sqlite3.connect(path)
    connection.executescript(
        """
        CREATE TABLE products (
            id INTEGER PRIMARY KEY,
            code TEXT,
            image_path TEXT,
            image_hash TEXT,
            image_url TEXT
        );
        CREATE TABLE scraped_products (
            id INTEGER PRIMARY KEY,
            code TEXT,
            image_path TEXT,
            image_url TEXT
        );
        CREATE TABLE sync_records (
            id INTEGER PRIMARY KEY,
            code TEXT,
            image_path TEXT,
            image_hash TEXT,
            image_url TEXT
        );
        """
    )
    connection.commit()
    connection.close()


def test_image_storage_audit_crosses_db_and_nested_roots(tmp_path: Path):
    project = tmp_path
    data_root = project / "data" / "images"
    products_root = data_root / "products"
    products_root.mkdir(parents=True)
    (data_root / "legacy.webp").write_bytes(b"legacy")
    (products_root / "P001.webp").write_bytes(b"same")
    (products_root / "duplicate.webp").write_bytes(b"same")
    (products_root / "P002.webp").write_bytes(b"used")

    db = project / "database" / "catalog.db"
    db.parent.mkdir()
    _create_db(db)

    used_hash = hashlib.sha256(b"used").hexdigest()
    connection = sqlite3.connect(db)
    connection.execute(
        "INSERT INTO products VALUES (?, ?, ?, ?, ?)",
        (1, "P001", "data/images/products/P001.webp", "", "u1"),
    )
    connection.execute(
        "INSERT INTO products VALUES (?, ?, ?, ?, ?)",
        (2, "P002", "data/images/products/P002.webp", used_hash, "u2"),
    )
    connection.execute(
        "INSERT INTO scraped_products VALUES (?, ?, ?, ?)",
        (1, "LEG", "data/images/legacy.webp", "u3"),
    )
    connection.execute(
        "INSERT INTO sync_records VALUES (?, ?, ?, ?, ?)",
        (1, "MISS", "data/images/missing.webp", "", "u4"),
    )
    connection.commit()
    connection.close()

    report = audit(
        project_root=project,
        db_path=db,
        roots=[data_root, products_root],
    )

    assert report["files_total"] == 4
    assert report["files_by_root"]["data/images"] == 1
    assert report["files_by_root"]["data/images/products"] == 3
    assert report["db_references_total"] == 4
    assert report["referenced_files"] == 3
    assert report["orphan_files"] == 1
    assert report["missing_references"] == 1
    assert report["hash_match_references"] == 1
    assert report["hash_missing_references"] == 2
    assert report["hash_mismatch_references"] == 0
    assert len(report["duplicate_groups"]) == 1
    assert not report["cross_root_duplicate_groups"]


def test_image_storage_audit_detects_cross_root_duplicate(tmp_path: Path):
    project = tmp_path
    canonical = project / "data" / "images" / "products"
    legacy = project / "legacy-images"
    canonical.mkdir(parents=True)
    legacy.mkdir()

    (canonical / "P001.webp").write_bytes(b"same")
    (legacy / "old.webp").write_bytes(b"same")

    db = project / "database" / "catalog.db"
    db.parent.mkdir()
    _create_db(db)

    report = audit(
        project_root=project,
        db_path=db,
        roots=[canonical, legacy],
    )

    assert report["files_total"] == 2
    assert len(report["cross_root_duplicate_groups"]) == 1
