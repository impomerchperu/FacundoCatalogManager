"""Compare the project and installed FCM catalogs without modifying either database.

Run from the repository root:
    python tools/audit_catalog_consolidation.py

The report is written to %TEMP%. No migration, repair, copy, or deletion is
performed. The output is evidence for deciding how to consolidate catalog data.
"""
from __future__ import annotations

import json
import os
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit

PROJECT_ROOT = Path.cwd().resolve()
PROJECT_DATABASE = PROJECT_ROOT / "database" / "catalog.db"
LOCALAPPDATA_VALUE = os.environ.get("LOCALAPPDATA")
if not LOCALAPPDATA_VALUE:
    raise SystemExit("No existe la variable de entorno LOCALAPPDATA.")
LOCALAPPDATA_DATABASE = (
    Path(LOCALAPPDATA_VALUE)
    / "FacundoCatalogManager"
    / "database"
    / "catalog.db"
)
TEMP = Path(os.environ.get("TEMP", str(Path.home())))
JSON_COLUMNS = {"color_stock", "legacy_colors", "gallery_images"}
IGNORED_PRODUCT_COLUMNS = {"id", "created_at"}
MAX_SAMPLES = 20


def _quote_identifier(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def normalize_code(value: object) -> str:
    """Normalize product codes for matching, preserving original values in reports."""
    return str(value or "").strip().upper()


def normalize_json_value(value: object, column: str) -> object:
    """Compare JSON-backed fields independent of key order and whitespace."""
    if column not in JSON_COLUMNS or not isinstance(value, str):
        return value
    try:
        parsed = json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return value.strip()
    return json.dumps(
        parsed, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )


def normalize_category_url(value: object) -> str:
    """Create a stable category key from a canonical URL."""
    raw = str(value or "").strip()
    if not raw:
        return ""
    parts = urlsplit(raw)
    if not parts.scheme and not parts.netloc:
        return raw.casefold().rstrip("/")
    path = parts.path.rstrip("/") or "/"
    return urlunsplit(
        (parts.scheme.casefold(), parts.netloc.casefold(), path, "", "")
    )


def _category_key(name: object, canonical_url: object = "") -> str:
    url_key = normalize_category_url(canonical_url)
    if url_key:
        return "url:" + url_key
    return "name:" + " ".join(str(name or "").split()).casefold()


def _readonly_connection(path: Path) -> sqlite3.Connection:
    uri = path.resolve().as_uri() + "?mode=ro"
    connection = sqlite3.connect(uri, uri=True, timeout=5)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA query_only = ON")
    return connection


def _latest_activity(
    connection: sqlite3.Connection,
    table_columns: dict[str, list[str]],
) -> dict[str, dict[str, str | None]]:
    """Capture latest timestamps that help compare data freshness."""
    candidate_columns = {
        "scraping_runs": ("started_at", "finished_at"),
        "scraping_history": ("started_at", "finished_at", "applied_at"),
        "download_history": ("downloaded_at", "created_at", "finished_at"),
    }
    result: dict[str, dict[str, str | None]] = {}
    for table, columns in candidate_columns.items():
        if table not in table_columns:
            continue
        available = [column for column in columns if column in table_columns[table]]
        if not available:
            continue
        quoted_table = _quote_identifier(table)
        timestamps: dict[str, str | None] = {}
        for column in available:
            quoted_column = _quote_identifier(column)
            value = connection.execute(
                f"SELECT MAX({quoted_column}) FROM {quoted_table}"
            ).fetchone()[0]
            timestamps[column] = str(value) if value is not None else None
        result[table] = timestamps
    return result


def _exclusive_product_samples(
    rows: dict[str, dict[str, Any]],
    codes: list[str],
) -> list[dict[str, Any]]:
    """Retain enough row fields to investigate exclusive product codes."""
    selected = (
        "code", "name", "category", "description", "stock", "color_stock",
        "price", "price_sample", "price_hundred", "price_thousand",
        "image_url", "image_path", "image_hash", "gallery_images",
    )
    result = []
    for code in codes[:MAX_SAMPLES]:
        row = rows.get(code, {})
        result.append(
            {
                field: _safe_value(row[field])
                for field in selected
                if field in row
            }
        )
    return result


def _normalize_description(value: object) -> str:
    """Normalize whitespace only; preserve technical words and punctuation."""
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _read_database(path: Path, label: str) -> dict[str, Any]:  # noqa: PLR0912
    result: dict[str, Any] = {
        "label": label,
        "path": str(path),
        "exists": path.is_file(),
        "size_bytes": path.stat().st_size if path.is_file() else None,
        "inspection": "not_started",
        "integrity": None,
        "schema_version": None,
        "user_version": None,
        "table_counts": {},
        "tables": {},
        "product_rows": {},
        "duplicate_normalized_codes": [],
        "category_labels": {},
        "relations": {},
        "product_table_available": False,
        "relations_available": False,
        "latest_activity": {},
    }
    if not path.is_file():
        result["inspection"] = "missing"
        return result

    connection: sqlite3.Connection | None = None
    try:
        connection = _readonly_connection(path)
        result["inspection"] = "opened_read_only"
        result["integrity"] = connection.execute(
            "PRAGMA integrity_check"
        ).fetchone()[0]
        result["user_version"] = connection.execute(
            "PRAGMA user_version"
        ).fetchone()[0]

        schema_rows = connection.execute(
            "SELECT name, type FROM sqlite_master "
            "WHERE type IN ('table', 'view') AND name NOT LIKE 'sqlite_%' "
            "ORDER BY type, name"
        ).fetchall()
        table_names = {
            str(row["name"]) for row in schema_rows if row["type"] == "table"
        }
        tables: dict[str, list[str]] = {}
        counts: dict[str, int | None] = {}
        for table_name in sorted(table_names, key=str.casefold):
            quoted = _quote_identifier(table_name)
            columns = [
                str(row["name"])
                for row in connection.execute(
                    f"PRAGMA table_info({quoted})"
                ).fetchall()
            ]
            tables[table_name] = columns
            try:
                counts[table_name] = int(
                    connection.execute(
                        f"SELECT COUNT(*) FROM {quoted}"
                    ).fetchone()[0]
                )
            except sqlite3.Error:
                counts[table_name] = None
        result["tables"] = tables
        result["table_counts"] = counts
        result["latest_activity"] = _latest_activity(connection, tables)

        if "schema_migrations" in table_names:
            columns = tables["schema_migrations"]
            if "version" in columns:
                result["schema_version"] = connection.execute(
                    "SELECT MAX(version) FROM schema_migrations"
                ).fetchone()[0]

        if "products" not in table_names or "code" not in tables["products"]:
            result["inspection"] = "missing_products_code"
            return result

        product_columns = tables["products"]
        result["product_table_available"] = True
        product_rows: dict[str, dict[str, Any]] = {}
        duplicate_codes: set[str] = set()
        id_to_code: dict[object, str] = {}
        select_columns = ", ".join(
            _quote_identifier(column) for column in product_columns
        )
        for row in connection.execute(f"SELECT {select_columns} FROM products"):
            raw = dict(row)
            code = normalize_code(raw.get("code"))
            if not code:
                continue
            if code in product_rows:
                duplicate_codes.add(code)
                continue
            product_rows[code] = raw
            if "id" in raw:
                id_to_code[raw["id"]] = code
        result["product_rows"] = product_rows
        result["duplicate_normalized_codes"] = sorted(duplicate_codes)

        category_id_to_key: dict[object, str] = {}
        category_labels: dict[str, str] = {}
        if "categories" in table_names:
            category_columns = tables["categories"]
            if "id" in category_columns and "name" in category_columns:
                select = ["id", "name"]
                if "canonical_url" in category_columns:
                    select.append("canonical_url")
                for row in connection.execute(
                    "SELECT "
                    + ", ".join(_quote_identifier(column) for column in select)
                    + " FROM categories"
                ):
                    name = str(row["name"] or "").strip()
                    canonical_url = (
                        row["canonical_url"]
                        if "canonical_url" in select
                        else ""
                    )
                    key = _category_key(name, canonical_url)
                    category_id_to_key[row["id"]] = key
                    category_labels.setdefault(key, name)
        result["category_labels"] = category_labels

        relations: dict[str, set[str]] = {}
        if "product_categories" in table_names:
            pc_columns = tables["product_categories"]
            if {"product_id", "category_id"}.issubset(pc_columns):
                for row in connection.execute(
                    "SELECT product_id, category_id FROM product_categories"
                ):
                    code = id_to_code.get(row["product_id"])
                    category_key = category_id_to_key.get(row["category_id"])
                    if code and category_key:
                        relations.setdefault(code, set()).add(category_key)
                result["relations_available"] = True

        if not result["relations_available"] and "category" in product_columns:
            import re

            for code, product in product_rows.items():
                raw_category = str(product.get("category") or "")
                keys = {
                    _category_key(part.strip())
                    for part in re.split(r"[,;|]", raw_category)
                    if part.strip()
                }
                if keys:
                    relations[code] = keys
            result["relations_available"] = True
            result["relation_source"] = "products.category"
        else:
            result["relation_source"] = (
                "product_categories"
                if result["relations_available"]
                else "unavailable"
            )
        result["relations"] = relations
    except (sqlite3.Error, OSError, ValueError) as exc:
        result["inspection"] = "error"
        result["error"] = f"{type(exc).__name__}: {exc}"
    finally:
        if connection is not None:
            connection.close()
    return result


def _safe_value(value: object) -> object:
    if isinstance(value, bytes):
        return {"bytes_hex_prefix": value[:24].hex(), "length": len(value)}
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _product_comparison(
    project: dict[str, Any], local: dict[str, Any]
) -> dict[str, Any]:
    project_rows = project.get("product_rows", {})
    local_rows = local.get("product_rows", {})
    if not isinstance(project_rows, dict) or not isinstance(local_rows, dict):
        return {"available": False, "reason": "No fue posible leer las tablas products."}
    if not project.get("product_table_available") or not local.get(
        "product_table_available"
    ):
        return {"available": False, "reason": "Una base no tiene products.code."}

    project_codes = set(project_rows)
    local_codes = set(local_rows)
    common_codes = project_codes & local_codes
    project_columns = set(project.get("tables", {}).get("products", []))
    local_columns = set(local.get("tables", {}).get("products", []))
    common_columns = sorted(
        (project_columns & local_columns) - IGNORED_PRODUCT_COLUMNS,
        key=str.casefold,
    )

    difference_counts: dict[str, int] = {}
    difference_samples: dict[str, list[dict[str, Any]]] = {}
    description_whitespace_only_codes: list[str] = []
    description_content_difference_samples: list[dict[str, Any]] = []
    for code in sorted(common_codes):
        project_row = project_rows[code]
        local_row = local_rows[code]
        for column in common_columns:
            project_value = normalize_json_value(project_row.get(column), column)
            local_value = normalize_json_value(local_row.get(column), column)
            if project_value == local_value:
                continue
            if column == "description":
                project_text = _normalize_description(project_value)
                local_text = _normalize_description(local_value)
                if project_text == local_text:
                    description_whitespace_only_codes.append(code)
                elif len(description_content_difference_samples) < MAX_SAMPLES:
                    description_content_difference_samples.append(
                        {
                            "code": code,
                            "project": _safe_value(project_value),
                            "localappdata": _safe_value(local_value),
                        }
                    )
            difference_counts[column] = difference_counts.get(column, 0) + 1
            samples = difference_samples.setdefault(column, [])
            if len(samples) < MAX_SAMPLES:
                samples.append(
                    {
                        "code": code,
                        "project": _safe_value(project_row.get(column)),
                        "localappdata": _safe_value(local_row.get(column)),
                    }
                )

    return {
        "available": True,
        "project_products": len(project_codes),
        "localappdata_products": len(local_codes),
        "common_products": len(common_codes),
        "only_in_project": sorted(project_codes - local_codes),
        "only_in_localappdata": sorted(local_codes - project_codes),
        "duplicate_normalized_codes_project": project.get(
            "duplicate_normalized_codes", []
        ),
        "duplicate_normalized_codes_localappdata": local.get(
            "duplicate_normalized_codes", []
        ),
        "common_product_columns_compared": common_columns,
        "field_difference_product_counts": difference_counts,
        "field_difference_samples": difference_samples,
        "description_whitespace_only_difference_products": len(
            description_whitespace_only_codes
        ),
        "description_whitespace_only_samples": description_whitespace_only_codes[:MAX_SAMPLES],
        "description_substantive_difference_products": (
            difference_counts.get("description", 0)
            - len(description_whitespace_only_codes)
        ),
        "description_substantive_difference_samples": description_content_difference_samples,
        "exclusive_product_samples_project": _exclusive_product_samples(
            project_rows, sorted(project_codes - local_codes)
        ),
        "exclusive_product_samples_localappdata": _exclusive_product_samples(
            local_rows, sorted(local_codes - project_codes)
        ),
    }


def _relation_comparison(
    project: dict[str, Any], local: dict[str, Any]
) -> dict[str, Any]:
    project_relations = project.get("relations", {})
    local_relations = local.get("relations", {})
    if not project.get("relations_available") or not local.get(
        "relations_available"
    ):
        return {
            "available": False,
            "project_source": project.get("relation_source", "unavailable"),
            "localappdata_source": local.get("relation_source", "unavailable"),
        }

    project_relations = {
        code: set(keys) for code, keys in project_relations.items()
    }
    local_relations = {code: set(keys) for code, keys in local_relations.items()}
    all_codes = set(project_relations) | set(local_relations)
    changed = []
    project_pair_count = sum(len(keys) for keys in project_relations.values())
    local_pair_count = sum(len(keys) for keys in local_relations.values())
    for code in sorted(all_codes):
        left = project_relations.get(code, set())
        right = local_relations.get(code, set())
        if left != right:
            changed.append(
                {
                    "code": code,
                    "only_in_project": sorted(left - right),
                    "only_in_localappdata": sorted(right - left),
                }
            )
    return {
        "available": True,
        "project_source": project.get("relation_source"),
        "localappdata_source": local.get("relation_source"),
        "project_relation_count": project_pair_count,
        "localappdata_relation_count": local_pair_count,
        "codes_with_different_categories": len(changed),
        "samples": changed[:MAX_SAMPLES],
        "sample_limit": MAX_SAMPLES,
    }


def build_report(project_path: Path, local_path: Path) -> dict[str, Any]:
    project = _read_database(project_path, "PROJECT")
    local = _read_database(local_path, "LOCALAPPDATA")
    project_tables = set(project.get("tables", {}))
    local_tables = set(local.get("tables", {}))
    shared_tables = project_tables & local_tables
    schema_differences: dict[str, Any] = {
        "tables_only_in_project": sorted(project_tables - local_tables),
        "tables_only_in_localappdata": sorted(local_tables - project_tables),
        "columns_only_in_project": {},
        "columns_only_in_localappdata": {},
    }
    project_columns_only: dict[str, list[str]] = {}
    local_columns_only: dict[str, list[str]] = {}
    for table in sorted(shared_tables, key=str.casefold):
        pcols = set(project["tables"][table])
        lcols = set(local["tables"][table])
        if pcols - lcols:
            project_columns_only[table] = sorted(pcols - lcols)
        if lcols - pcols:
            local_columns_only[table] = sorted(lcols - pcols)
    schema_differences["columns_only_in_project"] = project_columns_only
    schema_differences["columns_only_in_localappdata"] = local_columns_only

    project_categories = project.get("category_labels", {})
    local_categories = local.get("category_labels", {})
    project_category_keys = set(project_categories)
    local_category_keys = set(local_categories)
    category_differences = {
        "project_categories": len(project_category_keys),
        "localappdata_categories": len(local_category_keys),
        "only_in_project": [
            {"key": key, "name": project_categories[key]}
            for key in sorted(project_category_keys - local_category_keys)
        ],
        "only_in_localappdata": [
            {"key": key, "name": local_categories[key]}
            for key in sorted(local_category_keys - project_category_keys)
        ],
        "different_names_same_key": [
            {
                "key": key,
                "project": project_categories[key],
                "localappdata": local_categories[key],
            }
            for key in sorted(project_category_keys & local_category_keys)
            if project_categories[key] != local_categories[key]
        ],
    }

    return {
        "report_type": "FCM_READ_ONLY_CATALOG_CONSOLIDATION_AUDIT",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "runtime_path_policy": {
            "development_mode": "config.runtime_paths uses PROJECT_ROOT/database/catalog.db",
            "frozen_mode": "config.runtime_paths uses %LOCALAPPDATA%/FacundoCatalogManager/database/catalog.db",
            "note": "Both paths are inspected independently; this audit does not select, copy, or merge either database.",
        },
        "project_database": {
            key: value for key, value in project.items() if key not in {"product_rows", "category_labels", "relations"}
        },
        "localappdata_database": {
            key: value for key, value in local.items() if key not in {"product_rows", "category_labels", "relations"}
        },
        "schema_differences": schema_differences,
        "category_differences": category_differences,
        "product_differences": _product_comparison(project, local),
        "product_category_relation_differences": _relation_comparison(project, local),
        "safety": {
            "opened_sqlite_read_only": True,
            "database_rows_modified": False,
            "files_moved_copied_or_deleted": False,
            "automatic_migration_performed": False,
            "automatic_database_selection_performed": False,
            "next_step": (
                "Review the code-only, field and category-link differences. Choose the canonical data source and migration policy before changing either database."
            ),
        },
    }


def main() -> int:
    report = build_report(PROJECT_DATABASE, LOCALAPPDATA_DATABASE)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    output_path = TEMP / f"fcm_catalog_consolidation_audit_{stamp}.json"
    output_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )

    for key, database in (
        ("PROJECT", report["project_database"]),
        ("LOCALAPPDATA", report["localappdata_database"]),
    ):
        tables = database.get("table_counts", {})
        print(
            "DATABASE|"
            + key
            + "|exists="
            + str(database.get("exists"))
            + "|inspection="
            + str(database.get("inspection"))
            + "|integrity="
            + str(database.get("integrity"))
            + "|schema_version="
            + str(database.get("schema_version"))
            + "|products="
            + str(tables.get("products", "n/a"))
            + "|product_categories="
            + str(tables.get("product_categories", "n/a"))
        )

    for database_key in ("project_database", "localappdata_database"):
        database = report[database_key]
        print(
            "LATEST_ACTIVITY|"
            + str(database.get("label"))
            + "|"
            + json.dumps(
                database.get("latest_activity", {}),
                ensure_ascii=False,
                separators=(",", ":"),
            )
        )

    product_diff = report["product_differences"]
    if product_diff.get("available"):
        print(
            "PRODUCT_CODES|project="
            + str(product_diff.get("project_products"))
            + "|localappdata="
            + str(product_diff.get("localappdata_products"))
            + "|common="
            + str(product_diff.get("common_products"))
        )
        print(
            "ONLY_IN_PROJECT|"
            + json.dumps(product_diff.get("only_in_project"), ensure_ascii=False)
        )
        print(
            "ONLY_IN_LOCALAPPDATA|"
            + json.dumps(product_diff.get("only_in_localappdata"), ensure_ascii=False)
        )
        print(
            "PRODUCT_FIELD_DIFFERENCES|"
            + json.dumps(
                product_diff.get("field_difference_product_counts"),
                ensure_ascii=False,
                separators=(",", ":"),
            )
        )
        print(
            "DESCRIPTION_DIFF_CLASSIFICATION|whitespace_only="
            + str(product_diff.get("description_whitespace_only_difference_products"))
            + "|substantive="
            + str(product_diff.get("description_substantive_difference_products"))
        )
        print(
            "EXCLUSIVE_PRODUCTS_PROJECT|"
            + json.dumps(
                product_diff.get("exclusive_product_samples_project", []),
                ensure_ascii=False,
                separators=(",", ":"),
                default=str,
            )
        )
        print(
            "EXCLUSIVE_PRODUCTS_LOCALAPPDATA|"
            + json.dumps(
                product_diff.get("exclusive_product_samples_localappdata", []),
                ensure_ascii=False,
                separators=(",", ":"),
                default=str,
            )
        )
        print(
            "DESCRIPTION_SUBSTANTIVE_SAMPLES|"
            + json.dumps(
                product_diff.get("description_substantive_difference_samples", []),
                ensure_ascii=False,
                separators=(",", ":"),
                default=str,
            )
        )
        field_samples = product_diff.get("field_difference_samples", {})
        for column, samples in sorted(field_samples.items()):
            print(
                "PRODUCT_FIELD_SAMPLE|"
                + str(column)
                + "|"
                + json.dumps(
                    samples[:5],
                    ensure_ascii=False,
                    separators=(",", ":"),
                    default=str,
                )
            )
    else:
        print("PRODUCT_COMPARISON_UNAVAILABLE|" + str(product_diff.get("reason")))

    category_diff = report["category_differences"]
    print(
        "CATEGORY_DIFFERENCES|"
        + json.dumps(
            category_diff,
            ensure_ascii=False,
            separators=(",", ":"),
            default=str,
        )
    )

    relation_diff = report["product_category_relation_differences"]
    print(
        "CATEGORY_RELATIONS|available="
        + str(relation_diff.get("available"))
        + "|project="
        + str(relation_diff.get("project_relation_count", "n/a"))
        + "|localappdata="
        + str(relation_diff.get("localappdata_relation_count", "n/a"))
        + "|changed_codes="
        + str(relation_diff.get("codes_with_different_categories", "n/a"))
    )
    if relation_diff.get("available"):
        print(
            "CATEGORY_RELATION_SAMPLES|"
            + json.dumps(
                relation_diff.get("samples", [])[:20],
                ensure_ascii=False,
                separators=(",", ":"),
                default=str,
            )
        )
    print(f"REPORT_JSON|{output_path}")
    print("NO_DATABASE_OR_SOURCE_FILE_MODIFICATIONS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
