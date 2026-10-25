"""Audit cached product-page category evidence without mutating the catalog.

Run from the repository root:
    python tools/audit_product_source_evidence.py

The report reads only database/catalog.db and writes its JSON report to %TEMP%.
It does not fetch the website, update SQLite, repair products, or delete files.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import zlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlsplit, urlunsplit

from bs4 import BeautifulSoup

PROJECT_ROOT = Path.cwd().resolve()
PROJECT_DATABASE = PROJECT_ROOT / "database" / "catalog.db"
TEMP = Path(os.environ.get("TEMP", str(Path.home())))
DEFAULT_CODES = (
    "FB-1908",
    "FB-3024",
    "FB-4047",
    "FB-4048",
    "TPSTCB",
    "FB-2111",
)
CATEGORY_PATH = "/categoria-producto/"
AUTHORITATIVE_METHODS = {"woocommerce_posted_in", "labeled_category_block"}


def normalize_source_url(value: object) -> str:
    """Match the product-page cache key normalization."""
    parts = urlsplit(str(value or "").strip())
    return urlunsplit(
        (
            parts.scheme.casefold(),
            parts.netloc.casefold(),
            parts.path or "/",
            parts.query,
            "",
        )
    )


def normalize_category_url(value: object, base_url: str = "") -> str:
    """Normalize absolute or relative category links for comparison."""
    raw = str(value or "").strip()
    if not raw:
        return ""
    absolute = urljoin(base_url, raw)
    parts = urlsplit(absolute)
    path = parts.path.rstrip("/") or "/"
    return urlunsplit(
        (
            parts.scheme.casefold(),
            parts.netloc.casefold(),
            path,
            "",
            "",
        )
    )


def _unique_links(anchors: list[Any], base_url: str) -> list[dict[str, str]]:
    seen: set[str] = set()
    result: list[dict[str, str]] = []
    for anchor in anchors:
        href = str(anchor.get("href", "") or "").strip()
        url = normalize_category_url(href, base_url)
        if CATEGORY_PATH not in urlsplit(url).path.casefold() or url in seen:
            continue
        seen.add(url)
        name = re.sub(r"\s+", " ", anchor.get_text(" ", strip=True)).strip()
        result.append({"name": name, "url": url})
    return sorted(result, key=lambda item: (item["url"], item["name"].casefold()))


def extract_category_evidence(
    html: str,
    base_url: str = "",
) -> dict[str, Any]:
    """Extract product taxonomy links while avoiding global navigation links."""
    soup = BeautifulSoup(html or "", "html.parser")

    posted_in = soup.select(".posted_in")
    declared: list[dict[str, str]] = []
    if posted_in:
        declared = _unique_links(
            [anchor for node in posted_in for anchor in node.select("a[href]")],
            base_url,
        )
        if declared:
            return {
                "method": "woocommerce_posted_in",
                "authoritative": True,
                "declared_categories": declared,
                "unscoped_candidates": [],
            }

    labeled_nodes: list[Any] = []
    for node in soup.find_all(["div", "span", "p", "li"]):
        text = re.sub(r"\s+", " ", node.get_text(" ", strip=True)).strip()
        if not re.match(r"^categor[ií]as?\s*:", text, flags=re.IGNORECASE):
            continue
        if node.select("a[href]"):
            labeled_nodes.append(node)
    if labeled_nodes:
        # Prefer the smallest label container to avoid including nearby sections.
        node = min(
            labeled_nodes,
            key=lambda candidate: len(candidate.get_text(" ", strip=True)),
        )
        declared = _unique_links(node.select("a[href]"), base_url)
        if declared:
            return {
                "method": "labeled_category_block",
                "authoritative": True,
                "declared_categories": declared,
                "unscoped_candidates": [],
            }

    candidates = _unique_links(soup.select("a[href]"), base_url)
    return {
        "method": "unscoped_links_only" if candidates else "no_category_links_found",
        "authoritative": False,
        "declared_categories": [],
        "unscoped_candidates": candidates[:100],
    }


def _readonly_connection(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA query_only = ON")
    return connection


def _table_names(connection: sqlite3.Connection) -> set[str]:
    return {
        str(row[0])
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        )
    }


def _columns(connection: sqlite3.Connection, table: str) -> set[str]:
    return {
        str(row["name"])
        for row in connection.execute(f'PRAGMA table_info("{table}")')
    }


def _decode_gallery(value: object, primary_url: object) -> list[dict[str, Any]]:
    images: list[dict[str, Any]] = []
    main_url = str(primary_url or "").strip()
    if main_url:
        images.append({"source": "primary", "position": 1, "url": main_url})

    try:
        parsed = json.loads(str(value or "[]"))
    except (json.JSONDecodeError, TypeError):
        parsed = None
    if not isinstance(parsed, list):
        return images

    for item in parsed:
        if not isinstance(item, dict):
            continue
        url = str(item.get("url", "") or "").strip()
        if not url:
            continue
        images.append(
            {
                "source": str(item.get("source", "") or ""),
                "position": item.get("position"),
                "url": url,
                "image_path": str(item.get("image_path", "") or ""),
                "image_hash": str(item.get("image_hash", "") or ""),
            }
        )
    return images


def _source_urls_for_code(
    connection: sqlite3.Connection,
    tables: set[str],
    code: str,
    name: str,
) -> list[str]:
    if "scraped_products" not in tables:
        return []
    columns = _columns(connection, "scraped_products")
    if not {"url", "code"}.issubset(columns):
        return []

    order = ""
    if "updated_at" in columns:
        order = " ORDER BY updated_at DESC"
        if "id" in columns:
            order += ", id DESC"
    elif "id" in columns:
        order = " ORDER BY id DESC"

    rows = connection.execute(
        "SELECT url FROM scraped_products "
        "WHERE UPPER(TRIM(COALESCE(code, ''))) = ? "
        "AND TRIM(COALESCE(url, '')) <> ''"
        + order,
        (code.upper(),),
    ).fetchall()
    urls = [str(row["url"]).strip() for row in rows if str(row["url"] or "").strip()]
    if urls:
        return list(dict.fromkeys(urls))

    if "name" in columns:
        rows = connection.execute(
            "SELECT url FROM scraped_products "
            "WHERE LOWER(TRIM(COALESCE(name, ''))) = LOWER(TRIM(?)) "
            "AND TRIM(COALESCE(url, '')) <> ''"
            + order,
            (name,),
        ).fetchall()
        return list(
            dict.fromkeys(
                str(row["url"]).strip()
                for row in rows
                if str(row["url"] or "").strip()
            )
        )
    return []


def _cache_index(connection: sqlite3.Connection, tables: set[str]) -> dict[str, dict[str, Any]]:
    if "source_page_cache" not in tables:
        return {}
    columns = _columns(connection, "source_page_cache")
    required = {
        "normalized_url",
        "original_url",
        "effective_url",
        "html_zlib",
        "content_sha256",
        "fetched_at",
        "checked_at",
        "status_code",
    }
    if not required.issubset(columns):
        return {}

    index: dict[str, dict[str, Any]] = {}
    rows = connection.execute(
        "SELECT normalized_url, original_url, effective_url, html_zlib, "
        "content_sha256, fetched_at, checked_at, status_code "
        "FROM source_page_cache"
    ).fetchall()
    for row in rows:
        record = dict(row)
        for field in ("normalized_url", "original_url", "effective_url"):
            key = normalize_source_url(record.get(field, ""))
            if key:
                index.setdefault(key, record)
    return index


def _decode_cached_html(record: dict[str, Any]) -> str | None:
    try:
        return zlib.decompress(bytes(record["html_zlib"])).decode(
            "utf-8", errors="replace"
        )
    except (KeyError, TypeError, ValueError, zlib.error):
        return None


def _product_categories(
    connection: sqlite3.Connection,
    tables: set[str],
    product_id: int,
) -> list[dict[str, str]]:
    if not {"product_categories", "categories"}.issubset(tables):
        return []
    rows = connection.execute(
        """
        SELECT c.name, c.canonical_url
        FROM product_categories AS pc
        JOIN categories AS c ON c.id = pc.category_id
        WHERE pc.product_id = ?
        ORDER BY c.name COLLATE NOCASE, c.canonical_url
        """,
        (product_id,),
    ).fetchall()
    return [
        {
            "name": str(row["name"] or ""),
            "url": normalize_category_url(row["canonical_url"]),
        }
        for row in rows
    ]


def _source_page_evidence(
    urls: list[str],
    cache_index: dict[str, dict[str, Any]],
    master_category_urls: set[str],
    project_relation_urls: set[str],
) -> list[dict[str, Any]]:
    evidence: list[dict[str, Any]] = []
    seen_cache_keys: set[str] = set()
    for url in urls:
        cache_record = cache_index.get(normalize_source_url(url))
        if cache_record is None:
            evidence.append(
                {
                    "source_url": url,
                    "cache_status": "not_found",
                }
            )
            continue

        cache_key = str(cache_record.get("normalized_url", "") or "")
        if cache_key in seen_cache_keys:
            continue
        seen_cache_keys.add(cache_key)
        html = _decode_cached_html(cache_record)
        if html is None:
            evidence.append(
                {
                    "source_url": url,
                    "cache_status": "decompression_error",
                    "normalized_url": cache_key,
                    "fetched_at": cache_record.get("fetched_at"),
                    "checked_at": cache_record.get("checked_at"),
                }
            )
            continue

        categories = extract_category_evidence(
            html,
            str(cache_record.get("effective_url", "") or url),
        )
        declared_urls = {
            item["url"] for item in categories["declared_categories"]
        }
        known_declared = declared_urls & master_category_urls
        item: dict[str, Any] = {
            "source_url": url,
            "cache_status": "decoded",
            "normalized_url": cache_key,
            "effective_url": cache_record.get("effective_url"),
            "fetched_at": cache_record.get("fetched_at"),
            "checked_at": cache_record.get("checked_at"),
            "status_code": cache_record.get("status_code"),
            "content_sha256": cache_record.get("content_sha256"),
            **categories,
            "declared_categories_known_to_catalog": sorted(known_declared),
            "declared_categories_not_in_catalog_master": sorted(
                declared_urls - master_category_urls
            ),
        }
        if categories["authoritative"]:
            item["project_relations_absent_from_product_page"] = sorted(
                project_relation_urls - known_declared
            )
            item["page_categories_missing_from_project_relations"] = sorted(
                known_declared - project_relation_urls
            )
        else:
            item["comparison_status"] = "not_comparable_without_scoped_category_links"
        evidence.append(item)
    return evidence


def build_report(database_path: Path, codes: tuple[str, ...] | list[str]) -> dict[str, Any]:
    """Read target products, their stored page HTML and category relations."""
    report: dict[str, Any] = {
        "database": str(database_path),
        "inspection": "not_started",
        "integrity": None,
        "schema_version": None,
        "target_codes": [str(code).strip().upper() for code in codes],
        "products": [],
        "safety": {
            "database_opened_read_only": True,
            "database_rows_modified": False,
            "website_requests_made": False,
            "source_files_modified": False,
        },
    }
    if not database_path.is_file():
        report["inspection"] = "missing"
        return report

    connection: sqlite3.Connection | None = None
    try:
        connection = _readonly_connection(database_path)
        report["inspection"] = "opened_read_only"
        report["integrity"] = connection.execute(
            "PRAGMA integrity_check"
        ).fetchone()[0]
        tables = _table_names(connection)
        if "schema_migrations" in tables:
            latest = connection.execute(
                "SELECT MAX(version) FROM schema_migrations"
            ).fetchone()[0]
            report["schema_version"] = int(latest) if latest is not None else None

        cache_index = _cache_index(connection, tables)
        master_category_urls: set[str] = set()
        if "categories" in tables and {"canonical_url"}.issubset(
            _columns(connection, "categories")
        ):
            master_category_urls = {
                normalize_category_url(row[0])
                for row in connection.execute("SELECT canonical_url FROM categories")
                if normalize_category_url(row[0])
            }

        for requested_code in report["target_codes"]:
            product: dict[str, Any] = {
                "requested_code": requested_code,
                "product_status": "not_found_in_project_catalog",
                "source_page_evidence": [],
            }
            if "products" not in tables or "code" not in _columns(connection, "products"):
                product["product_status"] = "products_table_or_code_column_missing"
                report["products"].append(product)
                continue

            product_row = connection.execute(
                "SELECT * FROM products WHERE UPPER(TRIM(code)) = ? LIMIT 1",
                (requested_code,),
            ).fetchone()
            if product_row is None:
                report["products"].append(product)
                continue

            row = dict(product_row)
            product_id = int(row["id"]) if row.get("id") is not None else -1
            actual_code = str(row.get("code", "") or requested_code)
            relation_categories = _product_categories(
                connection,
                tables,
                product_id,
            )
            relation_urls = {item["url"] for item in relation_categories}
            product_info = {
                "code": actual_code,
                "name": str(row.get("name", "") or ""),
                "stock": row.get("stock"),
                "color_stock": row.get("color_stock"),
                "description": row.get("description"),
                "image_url": row.get("image_url"),
                "categories_in_project_relation_table": relation_categories,
                "gallery_images": _decode_gallery(
                    row.get("gallery_images"),
                    row.get("image_url"),
                ),
            }
            source_urls = _source_urls_for_code(
                connection,
                tables,
                actual_code,
                product_info["name"],
            )
            product["product_status"] = "found"
            product["product"] = product_info
            product["source_urls"] = source_urls
            product["source_page_evidence"] = _source_page_evidence(
                source_urls,
                cache_index,
                master_category_urls,
                relation_urls,
            )
            if not source_urls:
                product["source_url_status"] = "not_found_in_scraped_products"
            elif all(
                item.get("cache_status") == "not_found"
                for item in product["source_page_evidence"]
            ):
                product["source_url_status"] = "url_found_but_no_cached_page"
            report["products"].append(product)

    finally:
        if connection is not None:
            connection.close()
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--database",
        type=Path,
        default=PROJECT_DATABASE,
        help="Ruta a la BD que contiene source_page_cache (por defecto, database/catalog.db).",
    )
    parser.add_argument(
        "--codes",
        nargs="*",
        default=list(DEFAULT_CODES),
        help="Códigos que se auditarán; por defecto se revisan las anomalías actuales.",
    )
    args = parser.parse_args()
    database_path = args.database.resolve()
    if not database_path.is_file():
        raise SystemExit(f"No existe la base de datos indicada: {database_path}")

    report = build_report(database_path, args.codes)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    report_path = TEMP / f"fcm_product_source_evidence_audit_{stamp}.json"
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, default=str) + "\n",
        encoding="utf-8",
    )

    print(
        "SOURCE_EVIDENCE_AUDIT|"
        f"integrity={report.get('integrity')}|"
        f"schema_version={report.get('schema_version')}|"
        f"products={len(report.get('products', []))}|"
        "read_only=True"
    )
    for product in report["products"]:
        print(
            "PRODUCT_SOURCE_EVIDENCE|"
            + json.dumps(product, ensure_ascii=False, sort_keys=True, default=str)
        )
    print(f"REPORT_JSON|{report_path}")
    print(
        "NO_DATABASE_OR_SOURCE_FILE_MODIFICATIONS|"
        "database_rows_modified=False|website_requests_made=False"
    )
    return 0 if report.get("integrity") == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
