import sqlite3
from pathlib import Path

from tools.audit_catalog_consolidation import (
    _normalize_description,
    build_report,
    normalize_category_url,
    normalize_code,
    normalize_json_value,
)


def _create_catalog(
    path: Path,
    *,
    schema_version: int,
    products: list[tuple[int, str, str, str, str, str]],
    category_name: str,
    category_url: str,
    relation_codes: list[str],
    with_cache: bool = False,
) -> None:
    with sqlite3.connect(path) as connection:
        connection.executescript(
            """
            CREATE TABLE schema_migrations (
                version INTEGER PRIMARY KEY,
                applied_at TEXT,
                description TEXT
            );
            CREATE TABLE products (
                id INTEGER PRIMARY KEY,
                code TEXT NOT NULL,
                name TEXT NOT NULL,
                description TEXT,
                color_stock TEXT,
                created_at TEXT
            );
            CREATE TABLE categories (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                canonical_url TEXT NOT NULL
            );
            CREATE TABLE product_categories (
                product_id INTEGER NOT NULL,
                category_id INTEGER NOT NULL
            );
            CREATE TABLE scraping_runs (
                id INTEGER PRIMARY KEY,
                started_at TEXT,
                finished_at TEXT
            );
            CREATE TABLE scraping_history (
                id INTEGER PRIMARY KEY,
                started_at TEXT,
                finished_at TEXT,
                applied_at TEXT
            );
            """
        )
        activity_date = "2026-10-25" if schema_version == 6 else "2026-10-24"
        connection.execute(
            "INSERT INTO scraping_runs VALUES (?, ?, ?)",
            (1, activity_date + "T10:00:00", activity_date + "T10:30:00"),
        )
        connection.execute(
            "INSERT INTO scraping_history VALUES (?, ?, ?, ?)",
            (1, activity_date + "T10:00:00", activity_date + "T10:30:00", activity_date + "T10:30:01"),
        )
        connection.execute(
            "INSERT INTO schema_migrations VALUES (?, ?, ?)",
            (schema_version, "2026-10-25", "test schema"),
        )
        connection.execute(
            "INSERT INTO categories VALUES (1, ?, ?)",
            (category_name, category_url),
        )
        for product_id, code, name, description, color_stock, created_at in products:
            connection.execute(
                "INSERT INTO products VALUES (?, ?, ?, ?, ?, ?)",
                (product_id, code, name, description, color_stock, created_at),
            )
        product_ids = {
            code.strip().upper(): product_id
            for product_id, code, *_ in products
        }
        for code in relation_codes:
            connection.execute(
                "INSERT INTO product_categories VALUES (?, ?)",
                (product_ids[code.strip().upper()], 1),
            )
        if with_cache:
            connection.execute(
                "CREATE TABLE source_page_cache (normalized_url TEXT PRIMARY KEY)"
            )


def test_normalizers_match_codes_urls_and_json_without_data_loss() -> None:
    assert normalize_code(" fb-0001 ") == "FB-0001"
    assert _normalize_description("Line one\n   Line two") == "Line one Line two"
    assert normalize_category_url(
        "HTTPS://Example.test/category/a/?preview=1#details"
    ) == "https://example.test/category/a"
    assert normalize_json_value(
        '{"Rojo": 2, "Azul": 1}', "color_stock"
    ) == normalize_json_value(
        '{"Azul":1,"Rojo":2}', "color_stock"
    )
    assert normalize_json_value("not-json", "color_stock") == "not-json"


def test_build_report_compares_products_relations_and_schema_read_only(
    tmp_path: Path,
) -> None:
    project_db = tmp_path / "project.db"
    local_db = tmp_path / "local.db"
    products_project = [
        (1, "FB-0001", "Producto A", "Detalle vigente", '{"Rojo":2,"Azul":1}', "today"),
        (2, "FB-0002", "Solo proyecto", "Detalle", "{}", "today"),
        (3, "FB-0004", "Producto formato", "Detalle adicional\npara producto", "{}", "today"),
    ]
    products_local = [
        (1, "FB-0001", "Producto A", "Detalle anterior", '{"Azul": 1, "Rojo": 2}', "yesterday"),
        (2, "FB-0003", "Solo local", "Detalle", "{}", "yesterday"),
        (3, "FB-0004", "Producto formato", "Detalle adicional para producto", "{}", "yesterday"),
    ]
    _create_catalog(
        project_db,
        schema_version=6,
        products=products_project,
        category_name="Artículos Antiestrés",
        category_url="https://example.test/categoria/antiestres/",
        relation_codes=["FB-0001", "FB-0002", "FB-0004"],
        with_cache=True,
    )
    _create_catalog(
        local_db,
        schema_version=2,
        products=products_local,
        category_name="Articulos Antiestres",
        category_url="HTTPS://EXAMPLE.TEST/categoria/antiestres",
        relation_codes=["FB-0003", "FB-0004"],
    )

    project_bytes_before = project_db.read_bytes()
    local_bytes_before = local_db.read_bytes()
    report = build_report(project_db, local_db)

    product_diff = report["product_differences"]
    assert product_diff["available"] is True
    assert product_diff["project_products"] == 3
    assert product_diff["localappdata_products"] == 3
    assert product_diff["common_products"] == 2
    assert product_diff["only_in_project"] == ["FB-0002"]
    assert product_diff["only_in_localappdata"] == ["FB-0003"]
    assert product_diff["field_difference_product_counts"] == {
        "description": 2
    }
    assert product_diff["description_whitespace_only_difference_products"] == 1
    assert product_diff["description_substantive_difference_products"] == 1
    assert product_diff["exclusive_product_samples_project"][0]["code"] == "FB-0002"
    assert product_diff["exclusive_product_samples_localappdata"][0]["code"] == "FB-0003"
    assert "source_page_cache" in report["schema_differences"]["tables_only_in_project"]
    assert report["project_database"]["schema_version"] == 6
    assert report["localappdata_database"]["schema_version"] == 2
    assert report["project_database"]["latest_activity"]["scraping_runs"]["finished_at"] == "2026-10-25T10:30:00"
    assert report["localappdata_database"]["latest_activity"]["scraping_runs"]["finished_at"] == "2026-10-24T10:30:00"

    relation_diff = report["product_category_relation_differences"]
    assert relation_diff["available"] is True
    assert relation_diff["project_relation_count"] == 3
    assert relation_diff["localappdata_relation_count"] == 2
    assert relation_diff["codes_with_different_categories"] == 3

    assert project_db.read_bytes() == project_bytes_before
    assert local_db.read_bytes() == local_bytes_before
    assert report["safety"]["database_rows_modified"] is False
    assert report["safety"]["files_moved_copied_or_deleted"] is False


def test_missing_database_is_reported_without_creating_it(tmp_path: Path) -> None:
    project_db = tmp_path / "missing-project.db"
    local_db = tmp_path / "missing-local.db"

    report = build_report(project_db, local_db)

    assert report["project_database"]["exists"] is False
    assert report["localappdata_database"]["exists"] is False
    assert not project_db.exists()
    assert not local_db.exists()
