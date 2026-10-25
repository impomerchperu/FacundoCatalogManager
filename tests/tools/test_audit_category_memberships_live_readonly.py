from __future__ import annotations

import sqlite3
from pathlib import Path

from tools.audit_category_memberships_live_readonly import (
    build_target_results,
    read_database_memberships,
)


def _make_catalog(path: Path) -> None:
    with sqlite3.connect(path) as connection:
        connection.executescript(
            """
            CREATE TABLE products (
                id INTEGER PRIMARY KEY,
                code TEXT NOT NULL,
                name TEXT NOT NULL
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
            INSERT INTO products VALUES (1, 'FB-1908', 'Tarjeta PVC');
            INSERT INTO categories VALUES (
                1,
                'Artículos de Oficina',
                'https://example.test/categoria-producto/articulos-de-oficina/'
            );
            INSERT INTO categories VALUES (
                2,
                'Artículos Antiestrés',
                'https://example.test/categoria-producto/articulos-de-antiestres/'
            );
            INSERT INTO product_categories VALUES (1, 1);
            INSERT INTO product_categories VALUES (1, 2);
            """
        )


def test_read_database_memberships_is_read_only_and_normalizes_requested_codes(
    tmp_path: Path,
) -> None:
    database = tmp_path / "catalog.db"
    _make_catalog(database)
    before = database.read_bytes()

    integrity, memberships = read_database_memberships(
        database,
        ["fb-1908", "FB-4047"],
    )

    assert integrity == "ok"
    assert memberships["FB-1908"]["product_found"] is True
    assert memberships["FB-1908"]["name"] == "Tarjeta PVC"
    assert memberships["FB-1908"]["categories"] == [
        "Artículos Antiestrés",
        "Artículos de Oficina",
    ]
    assert memberships["FB-4047"]["product_found"] is False
    assert memberships["FB-4047"]["categories"] == []
    assert database.read_bytes() == before


def test_membership_comparison_keeps_incomplete_live_coverage_inconclusive() -> None:
    database_memberships = {
        "FB-1908": {
            "product_found": True,
            "name": "Tarjeta PVC",
            "categories": ["Artículos de Oficina", "Artículos Antiestrés"],
        }
    }
    live_memberships = {
        "FB-1908": {"artículos de oficina"},
    }

    result = build_target_results(
        ["FB-1908"],
        database_memberships,
        live_memberships,
        coverage_complete=False,
    )[0]

    assert result["database_relations_not_seen_live"] == ["Artículos Antiestrés"]
    assert result["live_relations_missing_from_database"] == []
    assert result["decision"] == "INCONCLUSIVE_INCOMPLETE_LIVE_COVERAGE"
    assert result["coverage_complete"] is False


def test_membership_comparison_reports_differences_only_as_review_candidates() -> None:
    database_memberships = {
        "FB-1908": {
            "product_found": True,
            "name": "Tarjeta PVC",
            "categories": ["Artículos de Oficina", "Artículos Antiestrés"],
        }
    }
    live_memberships = {
        "FB-1908": {"articulos de oficina", "Nuevos Productos"},
    }

    result = build_target_results(
        ["FB-1908"],
        database_memberships,
        live_memberships,
        coverage_complete=True,
    )[0]

    assert result["database_relations_not_seen_live"] == ["Artículos Antiestrés"]
    assert result["live_relations_missing_from_database"] == ["Nuevos Productos"]
    assert result["decision"] == "REVIEW_ONLY_COVERAGE_VERIFIED"
    assert result["coverage_complete"] is True
