from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path

from tools.audit_image_storage import _json_safe, audit


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
        CREATE TABLE scraping_product_occurrences (
            id INTEGER PRIMARY KEY,
            code TEXT,
            product_url TEXT
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
    assert report["missing_active_references"] == 0
    assert report["active_referenced_files"] == 2
    assert report["active_orphan_files"] == 2
    assert report["legacy_only_files"] == 1
    assert report["hash_match_references"] == 1
    assert report["hash_missing_references"] == 2
    assert report["hash_mismatch_references"] == 0
    assert len(report["duplicate_groups"]) == 0
    assert len(report["content_duplicate_groups"]) == 1
    assert len(report["same_content_unknown_source_groups"]) == 1
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

    connection = sqlite3.connect(db)
    source_url = "https://example.test/shared.webp"
    connection.execute(
        "INSERT INTO products VALUES (?, ?, ?, ?, ?)",
        (1, "P001", "data/images/products/P001.webp", "", source_url),
    )
    connection.execute(
        "INSERT INTO products VALUES (?, ?, ?, ?, ?)",
        (2, "P002", "legacy-images/old.webp", "", source_url),
    )
    connection.executemany(
        "INSERT INTO scraping_product_occurrences (code, product_url) "
        "VALUES (?, ?)",
        [
            ("P001", "https://example.test/shared-product"),
            ("P002", "https://example.test/shared-product"),
        ],
    )
    connection.commit()
    connection.close()

    report = audit(
        project_root=project,
        db_path=db,
        roots=[canonical, legacy],
    )

    assert report["files_total"] == 2
    assert len(report["cross_root_duplicate_groups"]) == 1




def test_image_storage_audit_keeps_identical_content_from_different_urls(
    tmp_path: Path,
):
    project = tmp_path
    root = project / "data" / "images" / "products"
    root.mkdir(parents=True)

    (root / "P001.webp").write_bytes(b"identical bytes")
    (root / "P002.webp").write_bytes(b"identical bytes")

    db = project / "database" / "catalog.db"
    db.parent.mkdir()
    _create_db(db)

    connection = sqlite3.connect(db)
    connection.execute(
        "INSERT INTO products VALUES (?, ?, ?, ?, ?)",
        (
            1, "P001", "data/images/products/P001.webp", "",
            "https://example.test/source-one.webp",
        ),
    )
    connection.execute(
        "INSERT INTO products VALUES (?, ?, ?, ?, ?)",
        (
            2, "P002", "data/images/products/P002.webp", "",
            "https://example.test/source-two.webp",
        ),
    )
    connection.executemany(
        "INSERT INTO scraping_product_occurrences (code, product_url) "
        "VALUES (?, ?)",
        [
            ("P001", "https://example.test/product-one"),
            ("P002", "https://example.test/product-two"),
        ],
    )
    connection.commit()
    connection.close()

    report = audit(
        project_root=project,
        db_path=db,
        roots=[root],
    )

    assert report["files_total"] == 2
    assert len(report["content_duplicate_groups"]) == 1
    assert report["duplicate_groups"] == []
    assert len(report["same_content_different_source_groups"]) == 1
    assert report["same_content_unknown_source_groups"] == []


def test_image_storage_audit_keeps_different_extraction_methods_separate(
    tmp_path: Path,
):
    project = tmp_path
    root = project / "data" / "images" / "products"
    root.mkdir(parents=True)

    (root / "P001.webp").write_bytes(b"shared image bytes")
    (root / "P002-01.webp").write_bytes(b"another primary image")
    (root / "P002-02.webp").write_bytes(b"shared image bytes")

    shared_url = "https://example.test/shared.webp"
    main_relative = "data/images/products/P001.webp"
    gallery_relative = "data/images/products/P002-02.webp"

    db = project / "database" / "catalog.db"
    db.parent.mkdir()
    _create_db(db)

    connection = sqlite3.connect(db)
    connection.execute(
        "ALTER TABLE products ADD COLUMN gallery_images TEXT"
    )
    connection.execute(
        """
        INSERT INTO products (
            id, code, image_path, image_hash, image_url, gallery_images
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            1, "P001", main_relative, "", shared_url, "[]",
        ),
    )
    gallery = [{
        "url": shared_url,
        "image_path": gallery_relative,
        "image_hash": hashlib.sha256(b"shared image bytes").hexdigest(),
        "position": 2,
        "source": "woocommerce-gallery",
    }]
    connection.execute(
        """
        INSERT INTO products (
            id, code, image_path, image_hash, image_url, gallery_images
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            2,
            "P002",
            "data/images/products/P002-01.webp",
            "",
            "https://example.test/another-primary.webp",
            json.dumps(gallery),
        ),
    )
    connection.executemany(
        "INSERT INTO scraping_product_occurrences (code, product_url) "
        "VALUES (?, ?)",
        [
            ("P001", "https://example.test/shared-product"),
            ("P002", "https://example.test/shared-product"),
        ],
    )
    connection.commit()
    connection.close()

    report = audit(
        project_root=project,
        db_path=db,
        roots=[root],
    )

    assert report["files_total"] == 3
    assert len(report["content_duplicate_groups"]) == 1
    assert report["duplicate_groups"] == []
    assert len(report["same_content_different_source_groups"]) == 1
    assert report["same_content_unknown_source_groups"] == []


def test_image_storage_audit_detects_same_code_with_multiple_extensions(tmp_path: Path):
    project = tmp_path
    root = project / "data" / "images" / "products"
    root.mkdir(parents=True)
    (root / "P001.jpg").write_bytes(b"old")
    (root / "P001.webp").write_bytes(b"new")

    db = project / "database" / "catalog.db"
    db.parent.mkdir()
    _create_db(db)

    report = audit(
        project_root=project,
        db_path=db,
        roots=[root],
    )

    assert len(report["same_code_variant_groups"]) == 1
    assert {
        record["path"].name for record in report["same_code_variant_groups"][0]
    } == {"P001.jpg", "P001.webp"}


def test_image_storage_audit_reports_legacy_only_file(tmp_path: Path):
    project = tmp_path
    root = project / "data" / "images" / "products"
    root.mkdir(parents=True)
    (root / "legacy.webp").write_bytes(b"legacy")

    db = project / "database" / "catalog.db"
    db.parent.mkdir()
    _create_db(db)

    connection = sqlite3.connect(db)
    connection.execute(
        "INSERT INTO scraped_products VALUES (?, ?, ?, ?)",
        (1, "LEG", "data/images/products/legacy.webp", "u1"),
    )
    connection.commit()
    connection.close()

    report = audit(
        project_root=project,
        db_path=db,
        roots=[root],
    )

    assert report["active_referenced_files"] == 0
    assert report["active_orphan_files"] == 1
    assert report["legacy_only_files"] == 1


def test_image_storage_audit_discovers_new_image_reference_table(tmp_path: Path):
    project = tmp_path
    root = project / "data" / "images" / "products"
    root.mkdir(parents=True)
    image = root / "P010.webp"
    image.write_bytes(b"image")

    db = project / "database" / "catalog.db"
    db.parent.mkdir()
    _create_db(db)

    connection = sqlite3.connect(db)
    connection.execute(
        "CREATE TABLE future_images "
        "(id INTEGER PRIMARY KEY, code TEXT, image_path TEXT)"
    )
    connection.execute(
        "INSERT INTO future_images VALUES (?, ?, ?)",
        (1, "P010", "data/images/products/P010.webp"),
    )
    connection.commit()
    connection.close()

    report = audit(
        project_root=project,
        db_path=db,
        roots=[root],
    )

    assert report["db_references_by_table"]["future_images"] == 1
    assert report["legacy_only_files"] == 1

def test_image_storage_audit_includes_product_gallery_image_paths(
    tmp_path: Path,
):
    project = tmp_path
    root = project / "data" / "images" / "products"
    product_dir = root / "P010"
    product_dir.mkdir(parents=True)

    (product_dir / "P010-01.webp").write_bytes(b"main image")
    (product_dir / "P010-02.webp").write_bytes(b"gallery image")
    (product_dir / "P010-03.webp").write_bytes(b"unreferenced image")

    main_relative = "data/images/products/P010/P010-01.webp"
    gallery_relative = "data/images/products/P010/P010-02.webp"
    missing_relative = "data/images/products/P010/P010-04.webp"

    gallery = [
        {
            "url": "https://example.test/P010.webp",
            "image_path": main_relative,
            "image_hash": hashlib.sha256(b"main image").hexdigest(),
            "position": 1,
            "source": "primary",
        },
        {
            "url": "https://example.test/P010-alternative.webp",
            "image_path": gallery_relative,
            "image_hash": hashlib.sha256(b"gallery image").hexdigest(),
            "position": 2,
            "source": "woocommerce-gallery",
        },
        {
            "url": "https://example.test/P010-missing.webp",
            "image_path": missing_relative,
            "image_hash": "",
            "position": 3,
            "source": "woocommerce-gallery",
        },
    ]

    db = project / "database" / "catalog.db"
    db.parent.mkdir()
    _create_db(db)

    connection = sqlite3.connect(db)
    connection.execute(
        "ALTER TABLE products ADD COLUMN gallery_images TEXT"
    )
    connection.execute(
        """
        INSERT INTO products (
            id, code, image_path, image_hash, image_url, gallery_images
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            1,
            "P010",
            main_relative,
            "",
            "https://example.test/P010.webp",
            json.dumps(gallery),
        ),
    )
    connection.commit()
    connection.close()

    report = audit(
        project_root=project,
        db_path=db,
        roots=[root],
    )

    assert report["files_total"] == 3
    assert report["db_references_by_table"]["products"] == 3
    assert report["referenced_files"] == 2
    assert report["orphan_files"] == 1
    assert report["active_referenced_files"] == 2
    assert report["active_orphan_files"] == 1
    assert report["missing_references"] == 1
    assert report["missing_active_references"] == 1
    assert report["hash_match_references"] == 2
    assert [
        record["path"].name
        for record in report["orphan_file_details"]
    ] == ["P010-03.webp"]

def test_json_safe_recursively_converts_paths_in_nested_groups():
    report = {
        "content_duplicate_groups": [[{
            "path": Path("data") / "images" / "P001.webp",
        }]],
        "nested_tuple": (Path("data") / "images" / "P002.webp",),
    }

    serialized = json.dumps(_json_safe(report))
    restored = json.loads(serialized)

    assert (
        restored["content_duplicate_groups"][0][0]["path"]
        == "data/images/P001.webp"
    )
    assert restored["nested_tuple"] == ["data/images/P002.webp"]

def test_image_storage_audit_uses_product_page_as_extraction_source(
    tmp_path: Path,
):
    project = tmp_path
    root = project / "data" / "images" / "products"
    root.mkdir(parents=True)

    (root / "P001.webp").write_bytes(b"same source image bytes")
    (root / "P002.webp").write_bytes(b"same source image bytes")

    db = project / "database" / "catalog.db"
    db.parent.mkdir()
    _create_db(db)

    shared_image_url = "https://example.test/shared-image.webp"
    connection = sqlite3.connect(db)
    connection.execute(
        "INSERT INTO products VALUES (?, ?, ?, ?, ?)",
        (1, "P001", "data/images/products/P001.webp", "", shared_image_url),
    )
    connection.execute(
        "INSERT INTO products VALUES (?, ?, ?, ?, ?)",
        (2, "P002", "data/images/products/P002.webp", "", shared_image_url),
    )
    connection.executemany(
        "INSERT INTO scraping_product_occurrences (code, product_url) "
        "VALUES (?, ?)",
        [
            ("P001", "https://example.test/product-one"),
            ("P002", "https://example.test/product-two"),
        ],
    )
    connection.commit()
    connection.close()

    report = audit(
        project_root=project,
        db_path=db,
        roots=[root],
    )

    assert report["files_total"] == 2
    assert len(report["content_duplicate_groups"]) == 1
    assert report["duplicate_groups"] == []
    assert len(report["same_content_different_source_groups"]) == 1
    assert report["same_content_unknown_source_groups"] == []
