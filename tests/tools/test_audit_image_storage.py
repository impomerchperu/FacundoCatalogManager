from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from tools.audit_image_storage import audit


def test_image_storage_audit_counts_gallery_json_references_and_unknown_suffix_orphans(
    tmp_path: Path,
):
    project = tmp_path
    image_root = project / "data" / "images"
    product_dir = image_root / "products" / "FB-4008"
    product_dir.mkdir(parents=True)
    active_gallery = product_dir / "FB-4008-02.asset"
    orphan = product_dir / "FB-OLD-01.bin"
    active_gallery.write_bytes(b"gallery asset bytes")
    orphan.write_bytes(b"orphan asset bytes")

    db_path = project / "database" / "catalog.db"
    db_path.parent.mkdir(parents=True)
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            """
            CREATE TABLE products (
                id INTEGER PRIMARY KEY,
                code TEXT,
                image_path TEXT,
                image_hash TEXT,
                image_url TEXT,
                gallery_images TEXT
            )
            """
        )
        connection.execute(
            """
            INSERT INTO products (
                code, image_path, image_hash, image_url, gallery_images
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (
                "FB-4008",
                "",
                "",
                "",
                json.dumps(
                    [
                        {
                            "url": "https://site.test/FB-4008-02.asset",
                            "image_path": "data/images/products/FB-4008/FB-4008-02.asset",
                            "image_hash": "",
                        }
                    ]
                ),
            ),
        )

    report = audit(
        project_root=project,
        db_path=db_path,
        roots=[image_root],
    )

    assert report["db_references_by_source"]["gallery_images"] == 1
    assert report["reference_errors"] == []
    assert report["orphan_files"] == 1
    assert report["active_orphan_files"] == 1
    assert [
        Path(record["path"]).name for record in report["orphan_file_details"]
    ] == ["FB-OLD-01.bin"]
    assert active_gallery.is_file()


def test_image_storage_audit_reports_malformed_gallery_json_instead_of_silently_ignoring_it(
    tmp_path: Path,
):
    project = tmp_path
    image_root = project / "data" / "images"
    product_dir = image_root / "products" / "FB-4008"
    product_dir.mkdir(parents=True)
    possibly_referenced = product_dir / "FB-4008-02.webp"
    possibly_referenced.write_bytes(b"maybe-active image bytes")

    db_path = project / "database" / "catalog.db"
    db_path.parent.mkdir(parents=True)
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            """
            CREATE TABLE products (
                id INTEGER PRIMARY KEY,
                code TEXT,
                image_path TEXT,
                gallery_images TEXT
            )
            """
        )
        connection.execute(
            "INSERT INTO products (code, image_path, gallery_images) VALUES (?, ?, ?)",
            ("FB-4008", "", "{invalid-json"),
        )

    report = audit(
        project_root=project,
        db_path=db_path,
        roots=[image_root],
    )

    assert len(report["reference_errors"]) == 1
    assert report["reference_errors"][0]["source"] == "gallery_images"
    assert "JSON inválido" in report["reference_errors"][0]["error"]
    assert possibly_referenced.is_file()
