from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from tools.audit_image_storage import audit


def _create_catalog(tmp_path: Path, gallery_images: str) -> Path:
    db_path = tmp_path / "database" / "catalog.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
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
            ("FB-4008", "", "", "", gallery_images),
        )
    return db_path


def test_audit_scans_unknown_suffixes_in_product_storage_and_reads_gallery_references(
    tmp_path: Path,
):
    image_root = tmp_path / "data" / "images"
    product_dir = image_root / "products" / "FB-4008"
    product_dir.mkdir(parents=True)
    active_gallery = product_dir / "FB-4008-02.asset"
    orphan = product_dir / "FB-OLD-01.bin"
    active_gallery.write_bytes(b"active gallery bytes")
    orphan.write_bytes(b"unreferenced legacy asset bytes")

    db_path = _create_catalog(
        tmp_path,
        json.dumps(
            [
                {
                    "url": "https://site.test/FB-4008-02.asset",
                    "image_path": (
                        "data/images/products/FB-4008/FB-4008-02.asset"
                    ),
                }
            ]
        ),
    )

    report = audit(
        project_root=tmp_path,
        db_path=db_path,
        roots=[image_root],
    )

    assert report["reference_audit_complete"] is True
    assert report["reference_errors"] == []
    assert report["files_total"] == 2
    assert report["db_references_total"] == 1
    assert report["orphan_files"] == 1
    assert [item["path"].name for item in report["orphan_file_details"]] == [
        "FB-OLD-01.bin"
    ]
    assert active_gallery.is_file()


def test_audit_marks_malformed_gallery_json_as_incomplete(tmp_path: Path):
    image_root = tmp_path / "data" / "images"
    product_dir = image_root / "products" / "FB-4008"
    product_dir.mkdir(parents=True)
    possibly_referenced = product_dir / "FB-4008-02.webp"
    possibly_referenced.write_bytes(b"possibly referenced image bytes")
    db_path = _create_catalog(tmp_path, "{invalid-json")

    report = audit(
        project_root=tmp_path,
        db_path=db_path,
        roots=[image_root],
    )

    assert report["reference_audit_complete"] is False
    assert len(report["reference_errors"]) == 1
    assert report["reference_errors"][0]["table"] == "products"
    assert report["reference_errors"][0]["code"] == "FB-4008"
    assert report["reference_errors"][0]["source"] == "gallery_images"
    assert "JSON inválido" in report["reference_errors"][0]["error"]
    # The image is shown as a tentative orphan, but the warning makes clear
    # that no destructive cleanup should use these counts as a complete audit.
    assert report["orphan_files"] == 1
    assert possibly_referenced.is_file()


def test_audit_reports_invalid_gallery_items_without_hiding_valid_references(
    tmp_path: Path,
):
    image_root = tmp_path / "data" / "images"
    product_dir = image_root / "products" / "FB-4008"
    product_dir.mkdir(parents=True)
    active_gallery = product_dir / "FB-4008-02.webp"
    active_gallery.write_bytes(b"active gallery bytes")
    db_path = _create_catalog(
        tmp_path,
        json.dumps(
            [
                None,
                {
                    "image_path": (
                        "data/images/products/FB-4008/FB-4008-02.webp"
                    )
                },
            ]
        ),
    )

    report = audit(
        project_root=tmp_path,
        db_path=db_path,
        roots=[image_root],
    )

    assert report["reference_audit_complete"] is False
    assert len(report["reference_errors"]) == 1
    assert report["reference_errors"][0]["position"] == 1
    assert report["reference_errors"][0]["error"] == "Entrada de galería inválida."
    assert report["db_references_total"] == 1
    assert report["orphan_files"] == 0
    assert active_gallery.is_file()
