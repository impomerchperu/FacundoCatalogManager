import json
import sqlite3
from pathlib import Path

from services.scraping.category_name_normalizer import normalize_category_name
from tools.audit_live_catalog_readonly import _read_catalog_readonly


def _database_under(root: Path) -> Path:
    database_path = root / "database" / "catalog.db"
    database_path.parent.mkdir(parents=True, exist_ok=True)
    return database_path


def test_readonly_audit_supports_legacy_schema_without_gallery_images(
    tmp_path: Path,
) -> None:
    database_path = _database_under(tmp_path / "installation")
    image_path = (
        database_path.parent.parent
        / "data"
        / "images"
        / "products"
        / "FB-1234.webp"
    )
    image_path.parent.mkdir(parents=True, exist_ok=True)
    image_path.write_bytes(b"test image")

    with sqlite3.connect(database_path) as connection:
        connection.execute(
            """
            CREATE TABLE products (
                id INTEGER PRIMARY KEY,
                code TEXT NOT NULL,
                name TEXT NOT NULL,
                category TEXT,
                image_path TEXT
            )
            """
        )
        connection.execute(
            """
            INSERT INTO products (code, name, category, image_path)
            VALUES (?, ?, ?, ?)
            """,
            (
                "FB-1234",
                "Producto prueba",
                "Artículos Antiestrés, Artículos de Oficina",
                "data/images/products/FB-1234.webp",
            ),
        )
        connection.execute(
            """
            CREATE TABLE product_images (
                id INTEGER PRIMARY KEY,
                product_id INTEGER NOT NULL,
                image_path TEXT NOT NULL,
                position INTEGER
            )
            """
        )
        connection.execute(
            """
            INSERT INTO product_images (id, product_id, image_path, position)
            VALUES (?, ?, ?, ?)
            """,
            (1, 1, "data/images/gallery/FB-1234-01.webp", 1),
        )

    products, relations, metrics = _read_catalog_readonly(database_path)

    assert set(products) == {"FB-1234"}
    assert metrics["products"] == 1
    assert metrics["relation_source"] == "products.category"
    assert metrics["relations_audit_available"] is True
    assert relations == {
        ("FB-1234", normalize_category_name("Artículos Antiestrés")),
        ("FB-1234", normalize_category_name("Artículos de Oficina")),
    }
    assert metrics["gallery_audit_available"] is False
    assert metrics["gallery_products"] is None
    assert metrics["gallery_entries"] is None
    assert metrics["primary_image_audit_available"] is True
    assert metrics["missing_primary_files"] == 0
    candidates = {
        candidate["table"]: candidate
        for candidate in metrics["image_schema_candidates"]
    }
    assert set(candidates) == {"product_images", "products"}
    assert candidates["product_images"]["rows"] == 1
    assert "image_path" in candidates["product_images"]["columns"]


def test_readonly_audit_checks_normalized_relations_and_gallery_files(
    tmp_path: Path,
) -> None:
    database_path = _database_under(tmp_path / "installation")
    image_path = (
        database_path.parent.parent
        / "data"
        / "images"
        / "gallery"
        / "FB-1234"
        / "FB-1234-01.webp"
    )
    image_path.parent.mkdir(parents=True, exist_ok=True)
    image_path.write_bytes(b"test gallery image")

    gallery = [
        {
            "url": "https://example.test/FB-1234-01.webp",
            "image_path": "data/images/gallery/FB-1234/FB-1234-01.webp",
            "position": 1,
        }
    ]
    with sqlite3.connect(database_path) as connection:
        connection.executescript(
            """
            CREATE TABLE products (
                id INTEGER PRIMARY KEY,
                code TEXT NOT NULL,
                name TEXT NOT NULL,
                category TEXT,
                image_path TEXT,
                gallery_images TEXT
            );
            CREATE TABLE categories (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL
            );
            CREATE TABLE product_categories (
                product_id INTEGER NOT NULL,
                category_id INTEGER NOT NULL
            );
            """
        )
        connection.execute(
            """
            INSERT INTO products
                (id, code, name, category, image_path, gallery_images)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                1,
                "FB-1234",
                "Producto prueba",
                "Artículos Antiestrés",
                "",
                json.dumps(gallery),
            ),
        )
        connection.execute(
            "INSERT INTO categories (id, name) VALUES (?, ?)",
            (1, "Artículos Antiestrés"),
        )
        connection.execute(
            "INSERT INTO product_categories (product_id, category_id) VALUES (?, ?)",
            (1, 1),
        )

    products, relations, metrics = _read_catalog_readonly(database_path)

    assert set(products) == {"FB-1234"}
    assert relations == {
        ("FB-1234", normalize_category_name("Artículos Antiestrés"))
    }
    assert metrics["relation_source"] == "product_categories"
    assert metrics["gallery_audit_available"] is True
    assert metrics["gallery_products"] == 1
    assert metrics["gallery_entries"] == 1
    assert metrics["missing_gallery_files"] == 0
    assert metrics["primary_image_audit_available"] is True
    assert metrics["missing_primary_files"] == 0
