"""Compare the persisted catalog against the latest scraping result artifact."""

from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DB_PATH = PROJECT_ROOT / "database" / "catalog.db"
RESULT_PATH = PROJECT_ROOT / "data" / "scraping_result.json"


def normalize_code(value: object) -> str:
    """Normalize only case and outer whitespace; keep the code body exact."""
    return str(value or "").strip().upper()


def load_result(path: Path = RESULT_PATH) -> dict:
    if not path.exists():
        raise SystemExit(
            f"No existe {path}. Ejecute primero un scraping."
        )
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Resultado de scraping inválido: {exc}") from exc
    if not isinstance(payload, dict):
        raise SystemExit("Resultado de scraping inválido: el documento no es un objeto JSON.")
    return payload


def load_catalog(db_path: Path = DB_PATH) -> dict[str, tuple[str, str]]:
    with sqlite3.connect(db_path) as db:
        rows = db.execute("SELECT code, name FROM products").fetchall()
    return {
        normalize_code(code): (str(code or ""), str(name or ""))
        for code, name in rows
        if normalize_code(code)
    }


def compare_catalog(
    result: dict,
    catalog: dict[str, tuple[str, str]],
) -> tuple[list[str], list[str]]:
    scraped = {
        normalize_code(code)
        for code in result.get("codes", [])
        if normalize_code(code)
    }
    missing = sorted(set(catalog) - scraped)
    new_codes = sorted(scraped - set(catalog))
    return missing, new_codes


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Compara el catálogo local con el último resultado de scraping."
    )
    parser.add_argument(
        "--snapshot",
        type=Path,
        default=RESULT_PATH,
        help="Ruta opcional a un scraping_result.json.",
    )
    args = parser.parse_args()

    result = load_result(args.snapshot)
    catalog = load_catalog()
    missing, new_codes = compare_catalog(result, catalog)

    print(f"Snapshot: {result.get('scraped_at', 'desconocido')}")
    print(f"Resultado exitoso: {bool(result.get('success'))}")
    print(f"Cobertura completa: {bool(result.get('coverage_complete'))}")
    print(f"Códigos scraping: {len(result.get('codes', []))}")
    print(f"Códigos DB: {len(catalog)}")
    print(f"DB sin coincidencia exacta: {len(missing)}")
    for code in missing:
        original, name = catalog[code]
        print(f"  AUSENTE EN SCRAPING | {original!r} | {name}")
    print(f"Códigos del scraping que no están en DB: {len(new_codes)}")
    for code in new_codes:
        print(f"  NUEVO | {code}")

    complete = bool(result.get("success")) and bool(result.get("coverage_complete"))
    if not complete:
        print(
            "ABORTADO: el resultado no representa un scraping FULL exitoso "
            "y no se autoriza ninguna poda."
        )
        return 2

    print(
        "SOLO DIAGNÓSTICO: esta herramienta no modifica la base de datos. "
        "La poda se gestiona dentro del flujo normalizado."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
