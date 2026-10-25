from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
import zlib
from pathlib import Path

from tools.audit_product_source_evidence import (
    build_report,
    extract_category_evidence,
    normalize_category_url,
    normalize_source_url,
)


def test_category_extraction_uses_product_taxonomy_not_global_navigation() -> None:
    html = """
    <html>
      <nav><a href="/categoria-producto/articulos-de-oficina/">Oficina</a></nav>
      <div class="product_meta">
        <span class="posted_in">
          Categorías:
          <a href="/categoria-producto/articulos-de-antiestres/">Antiestrés</a>
          <a href="https://example.test/categoria-producto/insumos-de-sublimacion/">
            Insumos de Sublimación
          </a>
        </span>
      </div>
    </html>
    """

    evidence = extract_category_evidence(
        html,
        "https://example.test/producto/fb-1908/",
    )

    assert evidence["method"] == "woocommerce_posted_in"
    assert evidence["authoritative"] is True
    assert [item["name"] for item in evidence["declared_categories"]] == [
        "Antiestrés",
        "Insumos de Sublimación",
    ]
    assert len(evidence["declared_categories"]) == 2
    assert evidence["unscoped_candidates"] == []


def test_labeled_category_block_fallback_is_scoped() -> None:
    html = """
    <html>
      <nav><a href="/categoria-producto/ignored/">Ignored menu item</a></nav>
      <section>
        <div class="product-categories">
          Categorías:
          <a href="/categoria-producto/maquinas-de-sublimacion/">
            Máquinas de Sublimación
          </a>
        </div>
      </section>
    </html>
    """

    evidence = extract_category_evidence(
        html,
        "https://example.test/producto/fb-3024/",
    )

    assert evidence["method"] == "labeled_category_block"
    assert evidence["authoritative"] is True
    assert evidence["declared_categories"] == [
        {
            "name": "Máquinas de Sublimación",
            "url": "https://example.test/categoria-producto/maquinas-de-sublimacion",
        }
    ]


def _create_database(
    path: Path,
    html: str,
    *,
    with_cache: bool = True,
    with_scraped_record: bool = True,
) -> None:
    product_url = "https://example.test/producto/fb-1908/"
    category_antiestres = "https://example.test/categoria-producto/articulos-de-antiestres/"
    category_office = "https://example.test/categoria-producto/articulos-de-oficina/"

    with sqlite3.connect(path) as connection:
        connection.executescript(
            """
            CREATE TABLE schema_migrations (
                version INTEGER PRIMARY KEY,
                applied_at TEXT NOT NULL,
                description TEXT NOT NULL
            );
            CREATE TABLE products (
                id INTEGER PRIMARY KEY,
                code TEXT NOT NULL,
                name TEXT NOT NULL,
                description TEXT,
                stock INTEGER DEFAULT 0,
                color_stock TEXT DEFAULT '{}',
                image_url TEXT,
                image_hash TEXT DEFAULT '',
                gallery_images TEXT DEFAULT '[]'
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
            CREATE TABLE scraped_products (
                id INTEGER PRIMARY KEY,
                source TEXT NOT NULL,
                url TEXT NOT NULL,
                code TEXT,
                name TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            """
        )
        connection.execute(
            "INSERT INTO schema_migrations VALUES (6, '2026-10-25', 'test')"
        )
        connection.execute(
            "INSERT INTO products VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                1,
                "FB-1908",
                "Tarjeta PVC CR80",
                "Detalle vigente",
                100,
                '{"Blanco":100}',
                "https://example.test/images/fb-1908.webp",
                "a" * 64,
                json.dumps(
                    [
                        {
                            "url": "https://example.test/images/extra.webp",
                            "image_path": "data/images/products/FB-1908/FB-1908-02.webp",
                            "image_hash": "b" * 64,
                            "position": 2,
                            "source": "woocommerce-gallery",
                        }
                    ]
                ),
            ),
        )
        connection.execute(
            "INSERT INTO categories VALUES (1, ?, ?)",
            ("Artículos Antiestrés", category_antiestres),
        )
        connection.execute(
            "INSERT INTO categories VALUES (2, ?, ?)",
            ("Artículos de Oficina", category_office),
        )
        connection.executemany(
            "INSERT INTO product_categories VALUES (?, ?)",
            [(1, 1), (1, 2)],
        )
        if with_scraped_record:
            connection.execute(
                "INSERT INTO scraped_products VALUES (?, ?, ?, ?, ?, ?)",
                (1, "test", product_url, "FB-1908", "Tarjeta PVC CR80", "2026-10-24"),
            )
        if with_cache:
            connection.execute(
                """
                CREATE TABLE source_page_cache (
                    normalized_url TEXT PRIMARY KEY,
                    original_url TEXT NOT NULL,
                    effective_url TEXT NOT NULL,
                    html_zlib BLOB NOT NULL,
                    content_sha256 TEXT NOT NULL,
                    fetched_at TEXT NOT NULL,
                    checked_at TEXT NOT NULL,
                    status_code INTEGER NOT NULL
                )
                """
            )
            connection.execute(
                "INSERT INTO source_page_cache VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    normalize_source_url(product_url),
                    product_url,
                    product_url,
                    sqlite3.Binary(zlib.compress(html.encode("utf-8"))),
                    "c" * 64,
                    "2026-10-24T10:00:00+00:00",
                    "2026-10-24T10:00:00+00:00",
                    200,
                ),
            )


def test_report_compares_cached_categories_and_does_not_modify_database(
    tmp_path: Path,
) -> None:
    database = tmp_path / "catalog.db"
    html = """
    <html>
      <nav><a href="/categoria-producto/articulos-de-oficina/">Menu Oficina</a></nav>
      <div class="product_meta">
        <span class="posted_in">
          Categorías:
          <a href="/categoria-producto/articulos-de-antiestres/">Artículos Antiestrés</a>
        </span>
      </div>
    </html>
    """
    _create_database(database, html)
    before = database.read_bytes()

    report = build_report(database, ["FB-1908"])
    product = report["products"][0]
    page = product["source_page_evidence"][0]

    assert report["inspection"] == "opened_read_only"
    assert report["integrity"] == "ok"
    assert report["schema_version"] == 6
    assert product["product_status"] == "found"
    assert page["cache_status"] == "decoded"
    assert page["method"] == "woocommerce_posted_in"
    assert page["project_relations_absent_from_product_page"] == [
        "https://example.test/categoria-producto/articulos-de-oficina"
    ]
    assert page["project_occurrence_relations_not_declared_in_taxonomy"] == [
        "https://example.test/categoria-producto/articulos-de-oficina"
    ]
    assert "not the same as occurrence-based category memberships" in page["relation_comparison_scope"]
    assert page["page_categories_missing_from_project_relations"] == []
    assert product["product"]["gallery_images"][1]["source"] == "woocommerce-gallery"
    assert report["safety"]["database_rows_modified"] is False
    assert database.read_bytes() == before


def test_report_marks_missing_cache_and_missing_products_without_creating_data(
    tmp_path: Path,
) -> None:
    database = tmp_path / "catalog.db"
    _create_database(database, "<html></html>", with_cache=False)
    before = database.read_bytes()

    report = build_report(database, ["FB-1908", "FB-4047"])
    assert report["products"][0]["source_url_status"] == "url_found_but_no_cached_page"
    assert report["products"][1]["product_status"] == "not_found_in_project_catalog"
    assert normalize_category_url(
        "/categoria-producto/insumos-de-sublimacion/",
        "https://example.test/producto/a/",
    ) == "https://example.test/categoria-producto/insumos-de-sublimacion"
    assert database.read_bytes() == before


def test_report_finds_cached_product_page_by_sku_without_scraped_product_row(
    tmp_path: Path,
) -> None:
    database = tmp_path / "catalog.db"
    html = """
    <html>
      <head><title>Tarjeta de PVC CR80</title></head>
      <body>
        <h1 class="product_title">Tarjeta de PVC CR80</h1>
        <span class="sku">FB-1908</span>
        <div class="product_meta">
          <span class="posted_in">
            Categorías:
            <a href="/categoria-producto/articulos-de-antiestres/">
              Artículos Antiestrés
            </a>
          </span>
        </div>
      </body>
    </html>
    """
    _create_database(database, html, with_scraped_record=False)
    before = database.read_bytes()

    report = build_report(database, ["FB-1908"])
    product = report["products"][0]

    assert product["source_url_status"] == "cached_product_page_found"
    assert product["source_url_match_basis"] == "explicit_sku_in_cached_html"
    assert product["source_urls"] == [
        "https://example.test/producto/fb-1908/"
    ]
    assert len(product["source_page_evidence"]) == 1
    page = product["source_page_evidence"][0]
    assert page["cache_status"] == "decoded"
    assert page["method"] == "woocommerce_posted_in"
    assert page["authoritative"] is True
    assert page["declared_categories"] == [
        {
            "name": "Artículos Antiestrés",
            "url": "https://example.test/categoria-producto/articulos-de-antiestres",
        }
    ]
    assert page["project_relations_absent_from_product_page"] == [
        "https://example.test/categoria-producto/articulos-de-oficina"
    ]
    assert database.read_bytes() == before


def test_report_compares_cached_source_gallery_without_mutating_database(
    tmp_path: Path,
) -> None:
    database = tmp_path / "catalog.db"
    html = """
    <html>
      <h1 class="product_title">Tarjeta PVC CR80</h1>
      <span class="sku">FB-1908</span>
      <div class="product_meta">
        <span class="posted_in">
          Categorías:
          <a href="/categoria-producto/articulos-de-antiestres/">
            Artículos Antiestrés
          </a>
        </span>
      </div>
      <div class="woocommerce-product-gallery">
        <a href="/wp-content/uploads/2025/08/FB-1908.webp">
          <img
            src="/wp-content/uploads/2025/08/FB-1908-300x300.webp"
            data-large_image="/wp-content/uploads/2025/08/FB-1908.webp"
            alt="Tarjeta PVC"
          />
        </a>
        <a href="/wp-content/uploads/2025/08/MEZCLADOR-CAMION-copia.webp">
          <img
            src="/wp-content/uploads/2025/08/MEZCLADOR-CAMION-copia.webp"
            alt="Imagen alternativa"
          />
        </a>
      </div>
    </html>
    """
    _create_database(database, html)
    before = database.read_bytes()

    product = build_report(database, ["FB-1908"])["products"][0]
    page = product["source_page_evidence"][0]
    source_urls = {item["url"] for item in page["source_gallery_images"]}

    assert "https://example.test/wp-content/uploads/2025/08/FB-1908.webp" in source_urls
    assert (
        "https://example.test/wp-content/uploads/2025/08/MEZCLADOR-CAMION-copia.webp"
        in source_urls
    )
    assert page["gallery_comparison_note"].startswith(
        "A URL present in the cached HTML proves it was supplied by that page"
    )
    assert database.read_bytes() == before

def test_script_help_runs_when_called_outside_repository_root(
    tmp_path: Path,
) -> None:
    repository_root = Path(__file__).resolve().parents[2]
    script = repository_root / "tools" / "audit_product_source_evidence.py"
    environment = os.environ.copy()
    environment.pop("PYTHONPATH", None)

    result = subprocess.run(
        [sys.executable, str(script), "--help"],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "--database" in result.stdout
    assert "--codes" in result.stdout

