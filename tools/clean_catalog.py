"""Limpieza controlada del catálogo local.

Elimina residuos de códigos generados por reglas antiguas y consolida
registros duplicados cuyo código real solo difiere por espacios/mayúsculas.
Por defecto funciona en modo simulación; usar --apply para modificar SQLite.
"""

from __future__ import annotations

import argparse
import sqlite3
from collections import defaultdict

from database.db_manager import DBManager

# Prefijos usados por reglas temporales/generadas. Los códigos reales de
# Facundo se conservan salvo que coincidan explícitamente con estos patrones.
LEGACY_GENERATED_PREFIXES = ("AUTO-", "GENERATED-", "GEN-")


def normalize_code(value: object) -> str:
    return " ".join(str(value or "").split()).strip().upper()


def is_legacy_generated(code: str) -> bool:
    return normalize_code(code).startswith(LEGACY_GENERATED_PREFIXES)


def find_cleanup_candidates(connection: sqlite3.Connection) -> tuple[list[sqlite3.Row], dict[str, list[sqlite3.Row]]]:
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
    db = DBManager(db_path)
    connection = db.connection
    generated, duplicates = find_cleanup_candidates(connection)
    duplicate_rows = [row for items in duplicates.values() for row in items[1:]]

    summary = {
        "legacy_generated": len(generated),
        "duplicate_records": len(duplicate_rows),
        "duplicate_groups": len(duplicates),
        "deleted": 0,
    }

    print(f"Códigos generados antiguos: {summary['legacy_generated']}")
    print(f"Grupos duplicados por código normalizado: {summary['duplicate_groups']}")
    print(f"Registros duplicados a eliminar: {summary['duplicate_records']}")

    if not apply:
        print("SIMULACIÓN: no se modificó la base. Use --apply para aplicar.")
        return summary

    connection.execute("BEGIN")
    try:
        generated_ids = [row["id"] for row in generated]
        if generated_ids:
            connection.executemany("DELETE FROM products WHERE id = ?", ((row_id,) for row_id in generated_ids))
            summary["deleted"] += len(generated_ids)

        for items in duplicates.values():
            survivor = items[0]
            survivor_categories = merge_categories([item["category"] for item in items])
            if survivor_categories != (survivor["category"] or ""):
                connection.execute(
                    "UPDATE products SET category = ? WHERE id = ?",
                    (survivor_categories, survivor["id"]),
                )
            duplicate_ids = [(item["id"],) for item in items[1:]]
            connection.executemany("DELETE FROM products WHERE id = ?", duplicate_ids)
            summary["deleted"] += len(duplicate_ids)

        connection.commit()
    except Exception:
        connection.rollback()
        raise

    print(f"Registros eliminados: {summary['deleted']}")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Limpia códigos generados y duplicados del catálogo local.")
    parser.add_argument("--apply", action="store_true", help="Aplica los cambios; sin esto solo simula.")
    parser.add_argument("--db", default=None, help="Ruta opcional al catalog.db.")
    args = parser.parse_args()
    clean_catalog(args.db, apply=args.apply)


if __name__ == "__main__":
    main()
