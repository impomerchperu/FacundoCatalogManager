"""Compare the persisted catalog against the most recent scraping code snapshot."""

from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DB_PATH = PROJECT_ROOT / "database" / "catalog.db"
SNAPSHOT_PATH = PROJECT_ROOT / "data" / "last_scraping_codes.json"


def normalize_code(value: object) -> str:
    """Normalize only case and outer whitespace; keep the code body exact."""
    return str(value or "").strip().upper()


def load_snapshot() -> dict:
    if not SNAPSHOT_PATH.exists():
        raise SystemExit(
            f"No existe {SNAPSHOT_PATH}. Ejecute primero un scraping completo."
        )
    try:
        return json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Snapshot inválido: {exc}") from exc


def load_catalog() -> dict[str, tuple[str, str]]:
    with sqlite3.connect(DB_PATH) as db:
        rows = db.execute("SELECT code, name FROM products").fetchall()
    return {
        normalize_code(code): (str(code or ""), str(name or ""))
        for code, name in rows
        if normalize_code(code)
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="Eliminar códigos ausentes del scraping.")
    args = parser.parse_args()

    snapshot = load_snapshot()
    scraped = {
        normalize_code(code)
        for code in snapshot.get("codes", [])
        if normalize_code(code)
    }
    catalog = load_catalog()
    missing = sorted(set(catalog) - scraped)
    new_codes = sorted(scraped - set(catalog))

    print(f"Snapshot: {snapshot.get('scraped_at', 'desconocido')}")
    print(f"Códigos scraping: {len(scraped)}")
    print(f"Códigos DB: {len(catalog)}")
    print(f"DB sin coincidencia exacta: {len(missing)}")
    for code in missing:
        original, name = catalog[code]
        print(f"  ELIMINAR | {original!r} | {name}")
    print(f"Códigos del scraping que no están en DB: {len(new_codes)}")
    for code in new_codes:
        print(f"  NUEVO | {code}")

    expected = int(snapshot.get("expected_unique_products", 0) or 0)
    complete = bool(snapshot.get("coverage_complete")) and len(scraped) >= expected
    if not complete:
        print("ABORTADO: el snapshot no tiene cobertura completa y no se eliminará nada.")
        return 2

    if not args.apply:
        print("SIMULACIÓN: no se modificó la base. Use --apply para eliminar los ausentes.")
        return 0

    if missing:
        with sqlite3.connect(DB_PATH) as db:
            db.execute("PRAGMA foreign_keys = ON")
            for code in missing:
                db.execute("DELETE FROM products WHERE UPPER(TRIM(code)) = ?", (code,))
            db.commit()
    print(f"ELIMINADOS: {len(missing)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
