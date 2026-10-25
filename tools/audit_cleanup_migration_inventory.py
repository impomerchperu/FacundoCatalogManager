"""Inventario de solo lectura para la auditoría de migración y limpieza de FCM.

Ejecutar desde la raíz del repositorio:
    python tools/audit_cleanup_migration_inventory.py

El informe JSON se escribe en %TEMP%. No modifica bases de datos ni archivos
del proyecto; no decide ni ejecuta eliminaciones.
"""
from __future__ import annotations

import json
import os
import sqlite3
import time
from collections.abc import Iterator
from datetime import datetime, timezone
from pathlib import Path

PROJECT = Path.cwd().resolve()
LOCALAPPDATA_VALUE = os.environ.get("LOCALAPPDATA")
if not LOCALAPPDATA_VALUE:
    raise SystemExit("No existe la variable de entorno LOCALAPPDATA de Windows.")
APPDATA = Path(LOCALAPPDATA_VALUE) / "FacundoCatalogManager"
TEMP = Path(os.environ.get("TEMP", str(Path.home())))

EXCLUDED_DIRS = {
    ".git", ".venv", "venv", "env", "__pycache__", ".pytest_cache",
    ".mypy_cache", ".ruff_cache", "node_modules", "dist", "build",
}
DB_SUFFIXES = {".db", ".sqlite", ".sqlite3"}
BACKUP_ENDINGS = (
    ".db.bak", ".db.backup", ".db.old", ".db.orig",
    ".sqlite.bak", ".sqlite.backup", ".sqlite3.bak", ".sqlite3.backup",
)


def walk_files(base: Path) -> Iterator[Path]:
    if not base.is_dir():
        return
    for root, dirs, filenames in os.walk(base, topdown=True, followlinks=False):
        dirs[:] = sorted(
            dirname
            for dirname in dirs
            if dirname.casefold() not in EXCLUDED_DIRS
            and not (Path(root) / dirname).is_symlink()
        )
        root_path = Path(root)
        for filename in filenames:
            path = root_path / filename
            if path.is_file() and not path.is_symlink():
                yield path


def file_metadata(path: Path, relative_to: Path) -> dict[str, object]:
    try:
        stat = path.stat()
        try:
            relative_path = str(path.relative_to(relative_to))
        except ValueError:
            relative_path = str(path)
        return {
            "path": str(path),
            "relative_path": relative_path,
            "size_bytes": stat.st_size,
            "modified_local": datetime.fromtimestamp(
                stat.st_mtime
            ).astimezone().isoformat(),
            "suffix": path.suffix.casefold(),
        }
    except OSError as exc:
        return {"path": str(path), "stat_error": str(exc)}


def is_database_candidate(path: Path) -> bool:
    if path.suffix.casefold() in DB_SUFFIXES:
        return True
    return path.name.casefold().endswith(BACKUP_ENDINGS)


def discover_database_candidates() -> list[Path]:
    candidates: dict[str, Path] = {}
    for base in (PROJECT, APPDATA):
        for path in walk_files(base):
            if is_database_candidate(path):
                candidates[str(path.resolve()).casefold()] = path
    return sorted(candidates.values(), key=lambda item: str(item).casefold())


def quote_identifier(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def inspect_database(path: Path) -> dict[str, object]:
    base = PROJECT if path.is_relative_to(PROJECT) else APPDATA
    result = file_metadata(path, base)
    result["inspection"] = "not_started"
    connection: sqlite3.Connection | None = None
    try:
        uri = path.resolve().as_uri() + "?mode=ro"
        connection = sqlite3.connect(uri, uri=True, timeout=3)
        connection.row_factory = sqlite3.Row
        result["inspection"] = "opened_read_only"
        result["sqlite_version"] = sqlite3.sqlite_version
        result["user_version"] = connection.execute(
            "PRAGMA user_version"
        ).fetchone()[0]
        result["application_id"] = connection.execute(
            "PRAGMA application_id"
        ).fetchone()[0]

        tables: list[dict[str, object]] = []
        objects: list[dict[str, object]] = []
        rows = connection.execute(
            "SELECT type, name, tbl_name, sql FROM sqlite_master "
            "WHERE name NOT LIKE 'sqlite_%' ORDER BY type, name"
        ).fetchall()

        for row in rows:
            item: dict[str, object] = {
                "type": row["type"],
                "name": row["name"],
                "table_name": row["tbl_name"],
            }
            if row["sql"]:
                item["sql"] = row["sql"]

            if row["type"] == "table":
                table_name = str(row["name"])
                quoted = quote_identifier(table_name)
                try:
                    row_count = connection.execute(
                        f"SELECT COUNT(*) FROM {quoted}"
                    ).fetchone()[0]
                except sqlite3.Error as exc:
                    row_count = None
                    item["count_error"] = str(exc)

                columns = [
                    {
                        "name": col["name"],
                        "type": col["type"],
                        "not_null": bool(col["notnull"]),
                        "default": col["dflt_value"],
                        "primary_key_position": col["pk"],
                    }
                    for col in connection.execute(
                        f"PRAGMA table_info({quoted})"
                    ).fetchall()
                ]
                foreign_keys = [
                    {
                        "referenced_table": fk["table"],
                        "from_column": fk["from"],
                        "to_column": fk["to"],
                        "on_update": fk["on_update"],
                        "on_delete": fk["on_delete"],
                    }
                    for fk in connection.execute(
                        f"PRAGMA foreign_key_list({quoted})"
                    ).fetchall()
                ]
                indexes = [
                    {
                        "name": index["name"],
                        "unique": bool(index["unique"]),
                        "origin": index["origin"],
                    }
                    for index in connection.execute(
                        f"PRAGMA index_list({quoted})"
                    ).fetchall()
                ]
                item["row_count"] = row_count
                item["columns"] = columns
                item["foreign_keys"] = foreign_keys
                item["indexes"] = indexes
                tables.append({
                    "name": table_name,
                    "row_count": row_count,
                    "column_count": len(columns),
                    "foreign_key_count": len(foreign_keys),
                    "index_count": len(indexes),
                })
            objects.append(item)

        result["tables_summary"] = tables
        result["objects"] = objects
        result["integrity_check"] = connection.execute(
            "PRAGMA integrity_check"
        ).fetchone()[0]
        result["inspection"] = "complete"
    except (sqlite3.Error, OSError, ValueError) as exc:
        result["inspection"] = "failed"
        result["error"] = f"{type(exc).__name__}: {exc}"
    finally:
        if connection is not None:
            connection.close()
    return result


def summarize_files(base: Path, label: str) -> dict[str, object]:
    if not base.is_dir():
        return {"label": label, "root": str(base), "exists": False}

    groups: dict[str, dict[str, object]] = {}
    total_files = 0
    total_bytes = 0
    newest = 0.0
    oldest = time.time()

    for path in walk_files(base):
        try:
            stat = path.stat()
        except OSError:
            continue

        total_files += 1
        total_bytes += stat.st_size
        newest = max(newest, stat.st_mtime)
        oldest = min(oldest, stat.st_mtime)
        relative = path.relative_to(base)
        top_directory = relative.parts[0] if len(relative.parts) > 1 else "(root files)"
        extension = path.suffix.casefold() or "(no extension)"
        key = f"{top_directory}|{extension}"
        group = groups.setdefault(key, {
            "top_directory": top_directory,
            "extension": extension,
            "file_count": 0,
            "total_bytes": 0,
            "samples": [],
        })
        group["file_count"] = int(group["file_count"]) + 1
        group["total_bytes"] = int(group["total_bytes"]) + stat.st_size
        samples = group["samples"]
        if isinstance(samples, list) and len(samples) < 5:
            samples.append(str(relative))

    sorted_groups = sorted(
        groups.values(),
        key=lambda group: (
            -int(group["total_bytes"]),
            str(group["top_directory"]).casefold(),
            str(group["extension"]),
        ),
    )
    return {
        "label": label,
        "root": str(base),
        "exists": True,
        "total_files": total_files,
        "total_bytes": total_bytes,
        "total_mib": round(total_bytes / (1024 * 1024), 3),
        "oldest_file_mtime_local": (
            datetime.fromtimestamp(oldest).astimezone().isoformat()
            if total_files else None
        ),
        "newest_file_mtime_local": (
            datetime.fromtimestamp(newest).astimezone().isoformat()
            if total_files else None
        ),
        "groups_by_top_directory_and_extension": sorted_groups,
    }


def main() -> int:
    if not (PROJECT / "database").is_dir():
        raise SystemExit(
            f"No se detecta la carpeta database desde {PROJECT}. "
            "Ejecuta el script desde C:\\Proyectos\\FacundoCatalogManager."
        )

    database_reports = [
        inspect_database(path) for path in discover_database_candidates()
    ]
    inventory_roots = [
        ("PROJECT_WHOLE_TREE_EXCLUDING_BUILD_CACHES", PROJECT),
        ("PROJECT_DATABASE", PROJECT / "database"),
        ("PROJECT_DATA", PROJECT / "data"),
        ("PROJECT_BACKUPS", PROJECT / "backups"),
        ("PROJECT_REPORTS", PROJECT / "reports"),
        ("PROJECT_EXPORTS", PROJECT / "exports"),
        ("PROJECT_LOGS", PROJECT / "logs"),
        ("PROJECT_CACHE", PROJECT / "cache"),
        ("LOCALAPPDATA_APP", APPDATA),
    ]
    file_reports = [
        summarize_files(path, label) for label, path in inventory_roots
    ]

    report = {
        "report_type": "FCM_READ_ONLY_CLEANUP_MIGRATION_INVENTORY",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "project_root": str(PROJECT),
        "localappdata_root": str(APPDATA),
        "safety": {
            "database_open_mode": "read-only",
            "files_moved_or_deleted": False,
            "database_rows_modified": False,
            "purpose": (
                "Evidence for migration, consolidation, quarantine and "
                "safe cleanup planning."
            ),
        },
        "database_candidate_count": len(database_reports),
        "databases": database_reports,
        "file_inventories": file_reports,
        "next_decision": (
            "Do not delete candidates based on this report alone. Compare "
            "live code paths, product keys, content and backups first."
        ),
    }
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    output_path = TEMP / f"fcm_cleanup_migration_inventory_{stamp}.json"
    output_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print("FCM_CLEANUP_INVENTORY_SUMMARY")
    print(f"PROJECT|{PROJECT}")
    print(f"LOCALAPPDATA|{APPDATA}")
    print(f"DATABASE_CANDIDATES|{len(database_reports)}")
    for database in database_reports:
        database_path = database.get("path", "?")
        state = database.get("inspection", "unknown")
        integrity = database.get(
            "integrity_check", database.get("error", "not_checked")
        )
        tables = database.get("tables_summary", [])
        table_counts = ", ".join(
            f"{table['name']}={table['row_count']}"
            for table in tables
            if isinstance(table, dict)
        )
        print(
            f"DATABASE|{state}|integrity={integrity}|{database_path}"
        )
        print(f"TABLE_COUNTS|{table_counts or '(no tables read)'}")
        if "error" in database:
            print(f"DATABASE_ERROR|{database['error']}")

    for inventory in file_reports:
        print(
            "FILE_TREE|"
            + str(inventory.get("label"))
            + f"|exists={inventory.get('exists')}"
            + f"|files={inventory.get('total_files', 0)}"
            + f"|MiB={inventory.get('total_mib', 0)}"
        )
    print(f"REPORT_JSON|{output_path}")
    print("NO_DATABASE_OR_FILE_MODIFICATIONS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
