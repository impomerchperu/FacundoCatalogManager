from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from tools.reconcile_category_memberships_from_audit import (
    apply_reported_repairs,
    build_repair_plans,
)


def _make_database(path: Path) -> None:
    with sqlite3.connect(path) as connection:
        connection.executescript(
            """
            CREATE TABLE products (
                id INTEGER PRIMARY KEY, code TEXT NOT NULL, name TEXT NOT NULL,
                stock INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE categories (
                id INTEGER PRIMARY KEY, name TEXT NOT NULL, canonical_url TEXT NOT NULL
            );
            CREATE TABLE product_categories (
                product_id INTEGER NOT NULL, category_id INTEGER NOT NULL,
                UNIQUE(product_id, category_id),
                FOREIGN KEY(product_id) REFERENCES products(id),
                FOREIGN KEY(category_id) REFERENCES categories(id)
            );
            INSERT INTO products VALUES (1, 'FB-1908', 'Tarjeta PVC CR80', 434200);
            INSERT INTO products VALUES (2, 'FB-4047', 'Foco Antiestrés', 100);
            INSERT INTO categories VALUES (
                1, 'Artículos de Oficina',
                'https://example.test/categoria-producto/articulos-de-oficina/'
            );
            INSERT INTO categories VALUES (
                2, 'Artículos Antiestrés',
                'https://example.test/categoria-producto/articulos-de-antiestres/'
            );
            INSERT INTO categories VALUES (
                3, 'Artículos de Escritorio',
                'https://example.test/categoria-producto/articulos-de-escritorio/'
            );
            INSERT INTO product_categories VALUES (1, 1);
            INSERT INTO product_categories VALUES (1, 2);
            INSERT INTO product_categories VALUES (1, 3);
            INSERT INTO product_categories VALUES (2, 2);
            """
        )


def _report(path: Path, *, complete: bool = True) -> dict[str, object]:
    categories = [
        {
            "category": f"Categoría {index}",
            "expected_occurrences": 1,
            "collected_cards": 1,
            "cards_without_code": 0,
            "count_matches": True,
        }
        for index in range(24)
    ]
    return {
        "report_type": "FCM_LIVE_CATEGORY_MEMBERSHIP_AUDIT_READ_ONLY",
        "database": str(path.resolve()),
        "integrity": "ok",
        "live_metrics": {
            "categories_expected": 24,
            "categories_found": 24,
            "expected_category_occurrences": 522,
            "collected_category_cards": 522,
            "category_count_gaps": False,
            "missing_code_card_count": 0,
            "coverage_complete": complete,
            "categories": categories,
        },
        "target_results": [
            {
                "code": "FB-1908",
                "name": "Tarjeta PVC CR80",
                "product_found_in_database": True,
                "database_categories": [
                    "Artículos de Oficina",
                    "Artículos Antiestrés",
                    "Artículos de Escritorio",
                ],
                "live_listing_categories": ["Artículos de Oficina"],
                "database_relations_not_seen_live": [
                    "Artículos Antiestrés",
                    "Artículos de Escritorio",
                ],
                "live_relations_missing_from_database": [],
                "coverage_complete": complete,
                "decision": (
                    "REVIEW_ONLY_COVERAGE_VERIFIED"
                    if complete
                    else "INCONCLUSIVE_INCOMPLETE_LIVE_COVERAGE"
                ),
            }
        ],
    }


def test_preview_plan_is_read_only_and_lists_only_wrong_relations(tmp_path: Path) -> None:
    database = tmp_path / "catalog.db"
    _make_database(database)
    before = database.read_bytes()
    connection = sqlite3.connect(database.resolve().as_uri() + "?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    try:
        plans = build_repair_plans(connection, _report(database), ["FB-1908"])
    finally:
        connection.close()

    assert len(plans) == 1
    plan = plans[0]
    assert plan.code == "FB-1908"
    assert [name for _, name in plan.remove] == [
        "Artículos Antiestrés",
        "Artículos de Escritorio",
    ]
    assert plan.add == ()
    assert plan.live_categories == ("Artículos de Oficina",)
    assert database.read_bytes() == before


def test_apply_makes_backup_and_changes_only_target_relations(tmp_path: Path) -> None:
    database = tmp_path / "catalog.db"
    _make_database(database)
    plans, backup = apply_reported_repairs(database, _report(database), ["FB-1908"])

    assert backup is not None and backup.is_file()
    assert len(plans) == 1 and plans[0].changed
    with sqlite3.connect(database) as connection:
        actual = connection.execute(
            """
            SELECT c.name FROM product_categories AS pc JOIN categories AS c
            ON c.id=pc.category_id WHERE pc.product_id=1
            """
        ).fetchall()
        stock = connection.execute("SELECT stock FROM products WHERE id=1").fetchone()[0]
        other = connection.execute(
            "SELECT category_id FROM product_categories WHERE product_id=2"
        ).fetchall()
        integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
    assert actual == [("Artículos de Oficina",)]
    assert stock == 434200
    assert other == [(2,)]
    assert integrity == "ok"

    with sqlite3.connect(backup) as connection:
        original = connection.execute(
            "SELECT category_id FROM product_categories WHERE product_id=1 ORDER BY category_id"
        ).fetchall()
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    assert original == [(1,), (2,), (3,)]


def test_incomplete_coverage_is_rejected_without_writing(tmp_path: Path) -> None:
    database = tmp_path / "catalog.db"
    _make_database(database)
    before = database.read_bytes()
    connection = sqlite3.connect(database.resolve().as_uri() + "?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    try:
        with pytest.raises(ValueError, match="Cobertura live incompleta"):
            build_repair_plans(connection, _report(database, complete=False), ["FB-1908"])
    finally:
        connection.close()
    assert database.read_bytes() == before


def test_stale_relations_are_rejected(tmp_path: Path) -> None:
    database = tmp_path / "catalog.db"
    _make_database(database)
    report = _report(database)
    with sqlite3.connect(database) as connection:
        connection.execute(
            "DELETE FROM product_categories WHERE product_id=1 AND category_id=3"
        )
    connection = sqlite3.connect(database.resolve().as_uri() + "?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    try:
        with pytest.raises(ValueError, match="cambió desde la auditoría"):
            build_repair_plans(connection, report, ["FB-1908"])
    finally:
        connection.close()


def test_report_cannot_be_used_against_a_different_database(tmp_path: Path) -> None:
    first = tmp_path / "first.db"
    second = tmp_path / "second.db"
    _make_database(first)
    _make_database(second)
    with pytest.raises(ValueError, match="no coincide"):
        apply_reported_repairs(second, _report(first), ["FB-1908"])
