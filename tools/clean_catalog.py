"""Diagnóstico de residuos legacy del catálogo local.

La herramienta es deliberadamente de solo lectura. La limpieza destructiva
de maestros y relaciones normalizadas se realiza desde el flujo de
sincronización, que conoce las relaciones históricas y sus invariantes.
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

# Ejecutar `python tools/clean_catalog.py` coloca `tools/` en sys.path, no la
# raíz del proyecto. Añadimos la raíz para que los imports de la aplicación
# funcionen igual que al ejecutar `python app.py`.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from database.db_manager import DBManager

# Prefijos usados por reglas temporales/generadas. Los códigos reales de
# Facundo se conservan salvo que coincidan explícitamente con estos patrones.
LEGACY_GENERATED_PREFIXES = ("AUTO-", "GENERATED-", "GEN-")


def normalize_code(value: object) -> str:
    return " ".join(str(value or "").split()).strip().upper()


def is_legacy_generated(code: str) -> bool:
    return normalize_code(code).startswith(LEGACY_GENERATED_PREFIXES)


def find_cleanup_candidates(
    connection: sqlite3.Connection,
) -> tuple[list[sqlite3.Row], dict[str, list[sqlite3.Row]]]:
    rows = connection.execute(
        "SELECT id, code, name, category FROM products ORDER BY id"
    ).fetchall()
    generated = [row for row in rows if is_legacy_generated(row["code"])]
    generated_ids = {row["id"] for row in generated}
    groups: dict[str, list[sqlite3.Row]] = defaultdict(list)
    for row in rows:
        if row["id"] in generated_ids:
            continue
        code = normalize_code(row["code"])
        if code:
            groups[code].append(row)
    duplicates = {code: items for code, items in groups.items() if len(items) > 1}
    return generated, duplicates


def merge_categories(values: list[str | None]) -> str:
    merged: list[str] = []
    seen: set[str] = set()
    for value in values:
        for category in str(value or "").split(","):
            normalized = category.strip()
            key = normalized.casefold()
            if normalized and key not in seen:
                seen.add(key)
                merged.append(normalized)
    return ", ".join(merged)


def clean_catalog(db_path: str | None = None, apply: bool = False) -> dict[str, int]:
    """Report legacy cleanup candidates without modifying SQLite.

    ``apply`` is retained only for backwards-compatible callers. Passing it
    now fails explicitly because direct deletion can invalidate normalized
    product/category relationships and historical occurrence traceability.
    """
    if apply:
        raise RuntimeError(
            "La limpieza destructiva directa está deshabilitada; "
            "use la sincronización normalizada del catálogo."
        )

    db = DBManager(db_path)
    connection = db.connection
    try:
        generated, duplicates = find_cleanup_candidates(connection)
        duplicate_rows = [
            row for items in duplicates.values() for row in items[1:]
        ]

        summary = {
            "legacy_generated": len(generated),
            "duplicate_records": len(duplicate_rows),
            "duplicate_groups": len(duplicates),
            "deleted": 0,
        }

        print(f"Códigos generados antiguos: {summary['legacy_generated']}")
        print(
            "Grupos duplicados por código normalizado: "
            f"{summary['duplicate_groups']}"
        )
        print(
            "Registros duplicados que requieren revisión: "
            f"{summary['duplicate_records']}"
        )
        print(
            "SOLO DIAGNÓSTICO: no se modificó la base de datos. "
            "La limpieza destructiva se gestiona dentro del flujo normalizado."
        )
        return summary
    finally:
        db.close()

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Diagnostica códigos generados y duplicados del catálogo local."
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Obsoleto: la limpieza destructiva directa está deshabilitada.",
    )
    parser.add_argument("--db", default=None, help="Ruta opcional al catalog.db.")
    args = parser.parse_args()
    clean_catalog(args.db, apply=args.apply)


if __name__ == "__main__":
    main()
