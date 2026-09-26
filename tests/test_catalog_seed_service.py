import sqlite3
from pathlib import Path

from services.catalog_seed_service import CatalogSeedService


def _create_empty_database(path: Path) -> None:
    with sqlite3.connect(path) as connection:
        connection.executescript(
            """
            CREATE TABLE products (id INTEGER PRIMARY KEY);
            CREATE TABLE scraping_history (id INTEGER PRIMARY KEY);
            """
        )


def _create_seed_database(path: Path) -> None:
    with sqlite3.connect(path) as connection:
        connection.executescript(
            """
            CREATE TABLE products (id INTEGER PRIMARY KEY);
            CREATE TABLE scraping_history (id INTEGER PRIMARY KEY);
            INSERT INTO products (id) VALUES (1), (2);
            INSERT INTO scraping_history (id) VALUES (1);
            """
        )


def test_seed_service_skips_development_mode(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "services.catalog_seed_service.is_frozen",
        lambda: False,
    )

    assert CatalogSeedService.seed_if_needed() is False


def test_seed_service_raises_when_seed_database_is_missing(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "services.catalog_seed_service.is_frozen",
        lambda: True,
    )
    missing = tmp_path / "missing.db"
    images = tmp_path / "images"
    images.mkdir()

    monkeypatch.setattr(
        CatalogSeedService,
        "SEED_DATABASE_PATH",
        missing,
    )
    monkeypatch.setattr(
        CatalogSeedService,
        "SEED_IMAGES_PATH",
        images,
    )

    try:
        CatalogSeedService.seed_if_needed()
    except RuntimeError as error:
        assert "base semilla" in str(error)
    else:
        raise AssertionError("Se esperaba RuntimeError")


def test_seed_service_restores_database_and_images(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "services.catalog_seed_service.is_frozen",
        lambda: True,
    )

    source_db = tmp_path / "seed.db"
    source_images = tmp_path / "seed-images"
    source_images.mkdir()
    (source_images / "products").mkdir()
    (source_images / "products" / "sample.jpg").write_bytes(b"image")
    _create_seed_database(source_db)

    destination_db = tmp_path / "user" / "database" / "catalog.db"
    destination_images = tmp_path / "user" / "data" / "images"

    monkeypatch.setattr(CatalogSeedService, "SEED_DATABASE_PATH", source_db)
    monkeypatch.setattr(CatalogSeedService, "SEED_IMAGES_PATH", source_images)
    monkeypatch.setattr(
        "services.catalog_seed_service.DATABASE_PATH",
        destination_db,
    )
    monkeypatch.setattr(
        "services.catalog_seed_service.DATA_DIR",
        destination_db.parents[1],
    )

    assert CatalogSeedService.seed_if_needed() is True
    assert destination_db.is_file()
    assert (
        destination_images / "products" / "sample.jpg"
    ).is_file()

    with sqlite3.connect(destination_db) as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM products"
        ).fetchone()[0] == 2
        assert connection.execute(
            "SELECT COUNT(*) FROM scraping_history"
        ).fetchone()[0] == 1


def test_seed_service_does_not_overwrite_existing_catalog(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "services.catalog_seed_service.is_frozen",
        lambda: True,
    )

    source_db = tmp_path / "seed.db"
    source_images = tmp_path / "seed-images"
    source_images.mkdir()
    (source_images / "products").mkdir()
    _create_seed_database(source_db)

    destination_db = tmp_path / "user" / "database" / "catalog.db"
    destination_db.parent.mkdir(parents=True)
    _create_empty_database(destination_db)
    with sqlite3.connect(destination_db) as connection:
        connection.execute("INSERT INTO products (id) VALUES (99)")
        connection.commit()

    monkeypatch.setattr(CatalogSeedService, "SEED_DATABASE_PATH", source_db)
    monkeypatch.setattr(CatalogSeedService, "SEED_IMAGES_PATH", source_images)
    monkeypatch.setattr(
        "services.catalog_seed_service.DATABASE_PATH",
        destination_db,
    )
    monkeypatch.setattr(
        "services.catalog_seed_service.DATA_DIR",
        destination_db.parents[1],
    )

    assert CatalogSeedService.seed_if_needed() is False

    with sqlite3.connect(destination_db) as connection:
        assert connection.execute(
            "SELECT id FROM products ORDER BY id"
        ).fetchall() == [(99,)]
