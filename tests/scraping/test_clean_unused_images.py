from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

import tools.clean_unused_images as cleaner_module
from tests.scraping.image_test_utils import image_bytes
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


def test_cleanup_after_gallery_update_removes_obsolete_duplicate_files(
    tmp_path: Path,
):
    import json

    project = tmp_path
    image_root = project / "data" / "images"
    product_dir = image_root / "products" / "FB-1507"
    old_product_dir = image_root / "products"
    old_gallery_dir = image_root / "gallery" / "FB-1507"
    product_dir.mkdir(parents=True)
    old_gallery_dir.mkdir(parents=True, exist_ok=True)

    active_primary = product_dir / "FB-1507-01.webp"
    active_scaled = product_dir / "FB-1507-02.webp"
    active_alternate = product_dir / "FB-1507-03.webp"
    active_primary.write_bytes(b"primary")
    active_scaled.write_bytes(b"scaled")
    active_alternate.write_bytes(b"alternate")

    old_primary = old_product_dir / "FB-1507.webp"
    old_gallery_scaled = old_gallery_dir / "FB-1507-01.webp"
    old_gallery_duplicate = old_gallery_dir / "FB-1507-02.webp"
    old_gallery_alternate = old_gallery_dir / "FB-1507-03.webp"
    old_primary.write_bytes(b"primary")
    old_gallery_scaled.write_bytes(b"scaled")
    old_gallery_duplicate.write_bytes(b"primary")
    old_gallery_alternate.write_bytes(b"alternate")

    db = project / "database" / "catalog.db"
    db.parent.mkdir()
    connection = sqlite3.connect(db)
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
        """
        INSERT INTO products (code, image_path, gallery_images)
        VALUES (?, ?, ?)
        """,
        (
            "FB-1507",
            "data/images/products/FB-1507/FB-1507-01.webp",
            json.dumps(
                [
                    {
                        "image_path": "data/images/products/FB-1507/FB-1507-01.webp",
                        "image_hash": "primary",
                        "position": 1,
                    },
                    {
                        "image_path": "data/images/products/FB-1507/FB-1507-02.webp",
                        "image_hash": "scaled",
                        "position": 2,
                    },
                    {
                        "image_path": "data/images/products/FB-1507/FB-1507-03.webp",
                        "image_hash": "alternate",
                        "position": 3,
                    },
                ]
            ),
        ),
    )
    connection.commit()
    connection.close()

    deleted = clean_unused_images(
        project_root=project,
        db_path=db,
        roots=["data/images"],
        delete=True,
    )

    assert {
        item["relative"] for item in deleted
    } == {
        "data/images/products/FB-1507.webp",
        "data/images/gallery/FB-1507/FB-1507-01.webp",
        "data/images/gallery/FB-1507/FB-1507-02.webp",
        "data/images/gallery/FB-1507/FB-1507-03.webp",
    }
    assert active_primary.is_file()
    assert active_scaled.is_file()
    assert active_alternate.is_file()
    assert not old_primary.exists()
    assert not old_gallery_scaled.exists()
    assert not old_gallery_duplicate.exists()
    assert not old_gallery_alternate.exists()


def test_cleanup_detects_decodable_image_with_unknown_suffix(tmp_path: Path):
    project = tmp_path
    root = project / "data" / "images"
    root.mkdir(parents=True)
    hidden_image = root / "legacy-image.asset"
    hidden_image.write_bytes(image_bytes("PNG", (11, 22, 33)))

    db = project / "database" / "catalog.db"
    db.parent.mkdir()
    _create_products_db(db)

    candidates = find_unused_images(
        project_root=project,
        db_path=db,
        roots=["data/images"],
    )

    assert [item["relative"] for item in candidates] == [
        "data/images/legacy-image.asset"
    ]


def test_unidentifiable_active_image_is_preserved_until_reference_is_removed(
    tmp_path: Path,
):
    project = tmp_path
    root = project / "data" / "images" / "products" / "P001"
    root.mkdir(parents=True)
    invalid = root / "P001-01.asset"
    invalid.write_bytes(b"not an identifiable image")

    db = project / "database" / "catalog.db"
    db.parent.mkdir()
    _create_products_db(db)
    _insert_product(db, "data/images/products/P001/P001-01.asset")

    deleted_while_referenced = clean_unused_images(
        project_root=project,
        db_path=db,
        roots=["data/images"],
        delete=True,
    )
    assert deleted_while_referenced == []
    assert invalid.is_file()

    with sqlite3.connect(db) as connection:
        connection.execute("UPDATE products SET image_path = ''")
        connection.commit()

    deleted_after_reference_removed = clean_unused_images(
        project_root=project,
        db_path=db,
        roots=["data/images"],
        delete=True,
    )
    assert [item["relative"] for item in deleted_after_reference_removed] == [
        "data/images/products/P001/P001-01.asset"
    ]
    assert not invalid.exists()


def test_cleanup_fails_closed_when_gallery_reference_json_is_malformed(
    tmp_path: Path,
):
    project = tmp_path
    root = project / "data" / "images"
    root.mkdir(parents=True)
    possibly_referenced = root / "possibly-active.webp"
    possibly_referenced.write_bytes(b"not an image, but still referenced")

    db = project / "database" / "catalog.db"
    db.parent.mkdir()
    connection = sqlite3.connect(db)
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
        ("P099", "", "{malformed-json"),
    )
    connection.commit()
    connection.close()

    with pytest.raises(RuntimeError, match="gallery_images no es JSON válido"):
        clean_unused_images(
            project_root=project,
            db_path=db,
            roots=["data/images"],
            delete=True,
        )

    assert possibly_referenced.is_file()


def test_cleanup_fails_closed_when_gallery_has_invalid_entry(tmp_path: Path):
    import json

    project = tmp_path
    root = project / "data" / "images"
    root.mkdir(parents=True)
    possibly_referenced = root / "possibly-active.webp"
    possibly_referenced.write_bytes(b"legacy image data")

    db = project / "database" / "catalog.db"
    db.parent.mkdir()
    connection = sqlite3.connect(db)
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
        ("P098", "", json.dumps([None])),
    )
    connection.commit()
    connection.close()

    with pytest.raises(TypeError, match="entrada de galería inválida"):
        clean_unused_images(
            project_root=project,
            db_path=db,
            roots=["data/images"],
            delete=True,
        )

    assert possibly_referenced.is_file()


def test_cleanup_rechecks_references_after_building_candidate_list(
    tmp_path: Path,
    monkeypatch,
):
    project = tmp_path
    root = project / "data" / "images"
    root.mkdir(parents=True)
    image_path = root / "newly-referenced.webp"
    image_path.write_bytes(b"artifact")

    db = project / "database" / "catalog.db"
    db.parent.mkdir()
    _create_products_db(db)

    original_find_unused = cleaner_module.find_unused_images

    def find_candidates_then_add_reference(**kwargs):
        candidates = original_find_unused(**kwargs)
        with sqlite3.connect(db) as connection:
            connection.execute(
                "INSERT INTO products (code, image_path) VALUES (?, ?)",
                ("P777", "data/images/newly-referenced.webp"),
            )
            connection.commit()
        return candidates

    monkeypatch.setattr(
        cleaner_module,
        "find_unused_images",
        find_candidates_then_add_reference,
    )

    deleted = clean_unused_images(
        project_root=project,
        db_path=db,
        roots=["data/images"],
        delete=True,
    )

    assert deleted == []
    assert image_path.is_file()


def test_cleanup_rechecks_gallery_reference_after_candidate_list(
    tmp_path: Path,
    monkeypatch,
):
    import json

    project = tmp_path
    root = project / "data" / "images"
    root.mkdir(parents=True)
    image_path = root / "newly-referenced-gallery.webp"
    image_path.write_bytes(b"artifact")

    db = project / "database" / "catalog.db"
    db.parent.mkdir()
    with sqlite3.connect(db) as connection:
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

    original_find_unused = cleaner_module.find_unused_images

    def find_candidates_then_add_gallery_reference(**kwargs):
        candidates = original_find_unused(**kwargs)
        with sqlite3.connect(db) as connection:
            connection.execute(
                "INSERT INTO products (code, image_path, gallery_images) "
                "VALUES (?, ?, ?)",
                (
                    "P778",
                    "",
                    json.dumps(
                        [{"image_path": "data/images/newly-referenced-gallery.webp"}]
                    ),
                ),
            )
        return candidates

    monkeypatch.setattr(
        cleaner_module,
        "find_unused_images",
        find_candidates_then_add_gallery_reference,
    )

    deleted = clean_unused_images(
        project_root=project,
        db_path=db,
        roots=["data/images"],
        delete=True,
    )

    assert deleted == []
    assert image_path.is_file()


def test_cleanup_checks_each_candidate_without_rebuilding_full_reference_snapshot(
    tmp_path: Path,
    monkeypatch,
):
    project = tmp_path
    root = project / "data" / "images"
    root.mkdir(parents=True)
    for index in range(80):
        (root / f"orphan-{index:03d}.webp").write_bytes(b"orphan")

    db = project / "database" / "catalog.db"
    db.parent.mkdir()
    _create_products_db(db)

    original_active_paths = cleaner_module._active_image_paths
    snapshot_calls = []

    def track_active_path_snapshot(db_path, project_root):
        snapshot_calls.append(db_path)
        return original_active_paths(db_path, project_root)

    monkeypatch.setattr(
        cleaner_module,
        "_active_image_paths",
        track_active_path_snapshot,
    )

    deleted = clean_unused_images(
        project_root=project,
        db_path=db,
        roots=["data/images"],
        delete=True,
    )

    assert len(deleted) == 80
    assert len(snapshot_calls) == 2


def test_cleanup_refreshes_reference_snapshot_after_concurrent_database_commit(
    tmp_path: Path,
    monkeypatch,
):
    project = tmp_path
    root = project / "data" / "images"
    root.mkdir(parents=True)
    first = root / "a-first.webp"
    second = root / "z-new-reference.webp"
    first.write_bytes(b"first")
    second.write_bytes(b"second")

    db = project / "database" / "catalog.db"
    db.parent.mkdir()
    _create_products_db(db)

    original_unlink = Path.unlink
    reference_added = []

    def unlink_first_then_reference_second(path, *args, **kwargs):
        if path.resolve() == first.resolve() and not reference_added:
            with sqlite3.connect(db) as connection:
                connection.execute(
                    "INSERT INTO products (code, image_path) VALUES (?, ?)",
                    ("P779", "data/images/z-new-reference.webp"),
                )
            reference_added.append(True)
        return original_unlink(path, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", unlink_first_then_reference_second)

    deleted = clean_unused_images(
        project_root=project,
        db_path=db,
        roots=["data/images"],
        delete=True,
    )

    assert [item["relative"] for item in deleted] == [
        "data/images/a-first.webp"
    ]
    assert not first.exists()
    assert second.is_file()


def test_cleanup_discovers_unidentifiable_artifact_in_product_folder(
    tmp_path: Path,
):
    project = tmp_path
    product_dir = project / "data" / "images" / "products" / "P777"
    product_dir.mkdir(parents=True)
    unidentifiable = product_dir / "P777-01.unknown"
    unidentifiable.write_bytes(b"unknown/corrupt image payload")

    db = project / "database" / "catalog.db"
    db.parent.mkdir()
    _create_products_db(db)

    candidates = find_unused_images(
        project_root=project,
        db_path=db,
        roots=["data/images"],
    )
    assert [item["relative"] for item in candidates] == [
        "data/images/products/P777/P777-01.unknown"
    ]

    deleted = clean_unused_images(
        project_root=project,
        db_path=db,
        roots=["data/images"],
        delete=True,
    )
    assert [item["relative"] for item in deleted] == [
        "data/images/products/P777/P777-01.unknown"
    ]
    assert not unidentifiable.exists()


def test_cleanup_does_not_discover_staging_artifacts_in_product_folder(
    tmp_path: Path,
):
    project = tmp_path
    staging = (
        project / "data" / "images" / "products" / "P778" / ".staging"
    )
    staging.mkdir(parents=True)
    temporary = staging / "P778-01.webp.tmp"
    temporary.write_bytes(b"temporary bytes")

    db = project / "database" / "catalog.db"
    db.parent.mkdir()
    _create_products_db(db)

    candidates = find_unused_images(
        project_root=project,
        db_path=db,
        roots=["data/images"],
    )

    assert candidates == []
    assert temporary.is_file()

def test_full_catalog_prune_cleans_real_primary_and_gallery_files_after_commit(
    tmp_path: Path,
):
    from database.db_manager import DBManager
    from models.product import Product
    from repositories.product_repository import ProductRepository
    from services.scraping.catalog_sync_service import CatalogSyncService
    from services.scraping.product_diff_service import ProductDiffService

    project = tmp_path
    db_path = project / "database" / "catalog.db"
    db_path.parent.mkdir(parents=True)
    image_root = project / "data" / "images" / "products" / "OLD001"
    image_root.mkdir(parents=True)

    primary = image_root / "OLD001-01.webp"
    gallery = image_root / "OLD001-02.png"
    primary.write_bytes(image_bytes("WEBP", (10, 20, 30)))
    gallery.write_bytes(image_bytes("PNG", (30, 20, 10)))

    db = DBManager(db_path=db_path)
    repository = ProductRepository(db)
    old = Product("OLD001", "Producto retirado", 10)
    old.image_path = "data/images/products/OLD001/OLD001-01.webp"
    old.image_hash = "primary-hash"
    old.gallery_images = [
        {
            "url": "https://site.test/OLD001-gallery.png",
            "image_path": "data/images/products/OLD001/OLD001-02.png",
            "image_hash": "gallery-hash",
            "position": 1,
        }
    ]
    repository.save(old)
    db.commit()

    cleanup_results: list[list[dict[str, object]]] = []

    def cleanup():
        with sqlite3.connect(db_path) as connection:
            row = connection.execute(
                "SELECT COUNT(*) FROM products WHERE code = ?",
                ("OLD001",),
            ).fetchone()
        assert row is not None and row[0] == 0

        deleted = clean_unused_images(
            project_root=project,
            db_path=db_path,
            roots=["data/images"],
            delete=True,
        )
        cleanup_results.append(deleted)
        return deleted

    service = CatalogSyncService(
        repository,
        ProductDiffService(),
        image_cleanup=cleanup,
    )
    result = service.sync_full_catalog(
        [Product("KEEP001", "Producto vigente", 20)],
        expected_products=1,
    )

    try:
        assert result.deleted == 1
        assert repository.get_by_code("OLD001") is None
        assert len(cleanup_results) == 1
        assert {
            str(item["relative"]) for item in cleanup_results[0]
        } == {
            "data/images/products/OLD001/OLD001-01.webp",
            "data/images/products/OLD001/OLD001-02.png",
        }
        assert not primary.exists()
        assert not gallery.exists()
    finally:
        db.close()
