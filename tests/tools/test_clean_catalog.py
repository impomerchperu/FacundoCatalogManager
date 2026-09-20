import sqlite3

import pytest

from database.db_manager import DBManager
from tools.clean_catalog import clean_catalog, find_cleanup_candidates, normalize_code


def test_normalize_code_keeps_body_and_canonicalizes_case():
    assert normalize_code("  fb-001  ") == "FB-001"


def test_find_cleanup_candidates_detects_generated_and_normalized_duplicates():
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.execute(
        "CREATE TABLE products (id INTEGER PRIMARY KEY, code TEXT, name TEXT, category TEXT)"
    )
    connection.executemany(
        "INSERT INTO products(id, code, name, category) VALUES (?, ?, ?, ?)",
        [
            (1, "AUTO-001", "Generado", "Legacy"),
            (2, " fb-001 ", "Original", "A"),
            (3, "FB-001", "Duplicado", "B"),
        ],
    )

    generated, duplicates = find_cleanup_candidates(connection)

    assert [row["code"] for row in generated] == ["AUTO-001"]
    assert list(duplicates) == ["FB-001"]
    assert [row["id"] for row in duplicates["FB-001"]] == [2, 3]

    connection.close()


def test_clean_catalog_is_read_only_and_reports_candidates(tmp_path, capsys):
    db_path = tmp_path / "catalog.db"
    db = DBManager(str(db_path))
    db.execute_query(
        "INSERT INTO products(code, name, category) VALUES (?, ?, ?)",
        ("AUTO-001", "Generado", "Legacy"),
    )
    db.close()

    summary = clean_catalog(str(db_path))

    assert summary == {
        "legacy_generated": 1,
        "duplicate_records": 0,
        "duplicate_groups": 0,
        "deleted": 0,
    }
    assert "SOLO DIAGNÓSTICO" in capsys.readouterr().out

    connection = sqlite3.connect(db_path)
    try:
        assert connection.execute("SELECT COUNT(*) FROM products").fetchone()[0] == 1
    finally:
        connection.close()


def test_clean_catalog_rejects_destructive_apply(tmp_path):
    with pytest.raises(RuntimeError, match="deshabilitada"):
        clean_catalog(str(tmp_path / "catalog.db"), apply=True)