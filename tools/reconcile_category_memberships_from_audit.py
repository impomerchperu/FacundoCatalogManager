"""Guarded reconciliation of product-category relations from complete live-list audits.

Preview is the default. Changes require --apply, a verified audit JSON, an SQLite
backup, and a transaction. Only explicitly selected product-category relations change.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from services.scraping.category_name_normalizer import normalize_category_name

REPORT_TYPE = "FCM_LIVE_CATEGORY_MEMBERSHIP_AUDIT_READ_ONLY"
VERIFIED_DECISION = "REVIEW_ONLY_COVERAGE_VERIFIED"


@dataclass(frozen=True)
class RepairPlan:
    code: str
    product_id: int
    product_name: str
    database_categories: tuple[str, ...]
    live_categories: tuple[str, ...]
    remove: tuple[tuple[int, str], ...]
    add: tuple[tuple[int, str], ...]
    live_keys: frozenset[str]

    @property
    def changed(self) -> bool:
        return bool(self.remove or self.add)

    def as_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "product_id": self.product_id,
            "product_name": self.product_name,
            "database_categories": list(self.database_categories),
            "live_listing_categories": list(self.live_categories),
            "remove_relations": [
                {"category_id": category_id, "category": name}
                for category_id, name in self.remove
            ],
            "add_relations": [
                {"category_id": category_id, "category": name}
                for category_id, name in self.add
            ],
            "changed": self.changed,
            "decision": VERIFIED_DECISION,
        }


def _readonly_connection(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA query_only = ON")
    return connection


def _key(value: object) -> str:
    return normalize_category_name(str(value or ""))


def _unique_names(values: object, context: str) -> dict[str, str]:
    if not isinstance(values, list):
        raise TypeError(f"{context}: se esperaba una lista de categorías.")
    result: dict[str, str] = {}
    for value in values:
        name = str(value or "").strip()
        key = _key(name)
        if not key:
            raise ValueError(f"{context}: se encontró una categoría vacía.")
        if key in result:
            raise ValueError(
                f"{context}: categorías duplicadas tras normalizar: "
                f"{result[key]!r} y {name!r}."
            )
        result[key] = name
    return result


def _validate_report(report: dict[str, Any]) -> None:
    if report.get("report_type") != REPORT_TYPE or report.get("integrity") != "ok":
        raise ValueError("El informe no es una auditoría de categorías íntegra y reconocida.")
    metrics = report.get("live_metrics")
    if not isinstance(metrics, dict):
        raise TypeError("El informe no contiene métricas de cobertura.")
    try:
        found = int(metrics.get("categories_found", 0))
        expected = int(metrics.get("categories_expected", 0))
        expected_cards = int(metrics.get("expected_category_occurrences", -1))
        cards = int(metrics.get("collected_category_cards", -2))
        missing_codes = int(metrics.get("missing_code_card_count", -1))
    except (TypeError, ValueError) as exc:
        raise ValueError("El informe contiene métricas inválidas.") from exc
    categories = metrics.get("categories")
    if (
        metrics.get("coverage_complete") is not True
        or metrics.get("category_count_gaps") is not False
        or found < 1
        or found != expected
        or expected_cards != cards
        or missing_codes != 0
        or not isinstance(categories, list)
        or len(categories) != found
    ):
        raise ValueError("Cobertura live incompleta; se cancela la reconciliación.")
    for category in categories:
        if (
            not isinstance(category, dict)
            or category.get("count_matches") is not True
            or int(category.get("cards_without_code", -1)) != 0
        ):
            raise ValueError("Hay discrepancias de cobertura o tarjetas sin código.")
    if not str(report.get("database", "")).strip():
        raise ValueError("El informe no identifica la base auditada.")


def load_report(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"No se pudo leer el informe {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise TypeError("El informe debe contener un objeto JSON.")
    _validate_report(value)
    return value


def _target_results(
    report: dict[str, Any], codes: list[str] | tuple[str, ...] | None
) -> dict[str, dict[str, Any]]:
    raw = report.get("target_results")
    if not isinstance(raw, list):
        raise TypeError("El informe no contiene target_results.")
    indexed: dict[str, dict[str, Any]] = {}
    for item in raw:
        if not isinstance(item, dict):
            raise TypeError("El informe contiene un destino inválido.")
        code = str(item.get("code", "") or "").strip().upper()
        if not code or code in indexed:
            raise ValueError(f"Código vacío o duplicado en el informe: {code!r}.")
        indexed[code] = item
    selected = (
        [str(code).strip().upper() for code in codes]
        if codes is not None
        else list(indexed)
    )
    selected = list(dict.fromkeys(code for code in selected if code))
    if not selected:
        raise ValueError("Debe indicar al menos un código.")
    absent = sorted(set(selected) - set(indexed))
    if absent:
        raise ValueError("El informe no contiene: " + ", ".join(absent))
    result: dict[str, dict[str, Any]] = {}
    for code in selected:
        item = indexed[code]
        if (
            item.get("decision") != VERIFIED_DECISION
            or item.get("coverage_complete") is not True
            or item.get("product_found_in_database") is not True
        ):
            raise ValueError(f"{code}: el informe no autoriza una revisión de cobertura completa.")
        result[code] = item
    return result


def build_repair_plans(
    connection: sqlite3.Connection,
    report: dict[str, Any],
    codes: list[str] | tuple[str, ...] | None = None,
) -> list[RepairPlan]:
    _validate_report(report)
    targets = _target_results(report, codes)
    tables = {
        str(row[0])
        for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }
    if not {"products", "categories", "product_categories"}.issubset(tables):
        raise ValueError("La base no contiene las tablas de catálogo necesarias.")

    category_rows = connection.execute("SELECT id, name FROM categories").fetchall()
    category_by_key: dict[str, tuple[int, str]] = {}
    for row in category_rows:
        name = str(row["name"] or "").strip()
        key = _key(name)
        if not key or key in category_by_key:
            raise ValueError(f"Nombre de categoría vacío o ambiguo: {name!r}.")
        category_by_key[key] = (int(row["id"]), name)

    plans: list[RepairPlan] = []
    for code, target in targets.items():
        products = connection.execute(
            "SELECT id, name FROM products WHERE UPPER(TRIM(COALESCE(code,'')))=?",
            (code,),
        ).fetchall()
        if len(products) != 1:
            raise ValueError(f"{code}: se encontraron {len(products)} productos en la base.")
        product_id = int(products[0]["id"])
        product_name = str(products[0]["name"] or "")
        actual_rows = connection.execute(
            """
            SELECT c.id, c.name FROM product_categories AS pc
            JOIN categories AS c ON c.id=pc.category_id
            WHERE pc.product_id=? ORDER BY c.name COLLATE NOCASE, c.id
            """,
            (product_id,),
        ).fetchall()
        actual_names = [str(row["name"] or "").strip() for row in actual_rows]
        actual = _unique_names(actual_names, f"relaciones de {code}")
        reported = _unique_names(target.get("database_categories"), f"informe DB de {code}")
        live = _unique_names(target.get("live_listing_categories"), f"listados live de {code}")
        if not live:
            raise ValueError(f"{code}: el listado no muestra ninguna categoría; operación rechazada.")
        if set(actual) != set(reported):
            raise ValueError(f"{code}: la DB cambió desde la auditoría; vuelva a auditar.")

        db_only = set(reported) - set(live)
        live_only = set(live) - set(reported)
        reported_db_only = _unique_names(
            target.get("database_relations_not_seen_live"), f"discrepancias DB de {code}"
        )
        reported_live_only = _unique_names(
            target.get("live_relations_missing_from_database"), f"discrepancias live de {code}"
        )
        if set(reported_db_only) != db_only or set(reported_live_only) != live_only:
            raise ValueError(f"{code}: discrepancias del informe inconsistentes; operación rechazada.")

        unknown = live_only - set(category_by_key)
        if unknown:
            raise ValueError(
                f"{code}: faltan categorías en la tabla maestra: "
                + ", ".join(live[key] for key in sorted(unknown))
            )
        actual_by_key = {
            _key(row["name"]): (int(row["id"]), str(row["name"] or "").strip())
            for row in actual_rows
        }
        remove = tuple(sorted((actual_by_key[key] for key in db_only), key=lambda item: item[1].casefold()))
        add = tuple(sorted((category_by_key[key] for key in live_only), key=lambda item: item[1].casefold()))
        plans.append(
            RepairPlan(
                code=code,
                product_id=product_id,
                product_name=product_name,
                database_categories=tuple(sorted(actual_names, key=str.casefold)),
                live_categories=tuple(sorted(live.values(), key=str.casefold)),
                remove=remove,
                add=add,
                live_keys=frozenset(live),
            )
        )
    return plans


def _make_backup(connection: sqlite3.Connection) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
    path = Path(tempfile.gettempdir()) / f"fcm_catalog_before_category_repair_{stamp}.db"
    destination = sqlite3.connect(path)
    try:
        connection.backup(destination)
        result = str(destination.execute("PRAGMA integrity_check").fetchone()[0])
        if result != "ok":
            raise RuntimeError(f"La copia de seguridad no es íntegra: {result}")
    finally:
        destination.close()
    return path


def apply_reported_repairs(  # noqa: PLR0912
    database_path: Path,
    report: dict[str, Any],
    codes: list[str] | tuple[str, ...] | None = None,
) -> tuple[list[RepairPlan], Path | None]:
    database = database_path.expanduser().resolve()
    reported_database = Path(str(report.get("database", ""))).expanduser().resolve()
    if database != reported_database:
        raise ValueError("La ruta de la DB no coincide con la base auditada.")

    connection = sqlite3.connect(database, timeout=30)
    connection.row_factory = sqlite3.Row
    backup: Path | None = None
    try:
        connection.execute("PRAGMA foreign_keys=ON")
        initial_data_version = int(
            connection.execute("PRAGMA data_version").fetchone()[0]
        )
        initial_plans = build_repair_plans(connection, report, codes)
        changed = [plan for plan in initial_plans if plan.changed]
        if not changed:
            return initial_plans, None

        # Back up before opening a write transaction; verify no other connection
        # changed the database between the backup and acquiring the write lock.
        backup = _make_backup(connection)
        backup_data_version = int(
            connection.execute("PRAGMA data_version").fetchone()[0]
        )
        if backup_data_version != initial_data_version:
            raise RuntimeError("La base cambió durante la copia; vuelva a auditar.")  # noqa: TRY301

        connection.execute("BEGIN IMMEDIATE")
        locked_data_version = int(
            connection.execute("PRAGMA data_version").fetchone()[0]
        )
        if locked_data_version != backup_data_version:
            raise RuntimeError(  # noqa: TRY301
                "La base cambió antes de bloquearla; no se aplicó ningún cambio."
            )
        integrity = str(connection.execute("PRAGMA integrity_check").fetchone()[0])
        if integrity != "ok":
            raise ValueError(f"integrity_check antes de reparar: {integrity}")  # noqa: TRY301
        plans = build_repair_plans(connection, report, codes)
        if plans != initial_plans:
            raise RuntimeError(  # noqa: TRY301
                "El plan cambió mientras se preparaba la reparación; vuelva a auditar."
            )
        changed = [plan for plan in plans if plan.changed]
        for plan in changed:
            for category_id, name in plan.remove:
                cursor = connection.execute(
                    "DELETE FROM product_categories WHERE product_id=? AND category_id=?",
                    (plan.product_id, category_id),
                )
                if cursor.rowcount != 1:
                    raise RuntimeError(f"{plan.code}: no se pudo retirar la relación {name!r}.")  # noqa: TRY301
            for category_id, name in plan.add:
                try:
                    connection.execute(
                        "INSERT INTO product_categories(product_id, category_id) VALUES (?,?)",
                        (plan.product_id, category_id),
                    )
                except sqlite3.IntegrityError as exc:
                    raise RuntimeError(f"{plan.code}: no se pudo agregar la relación {name!r}.") from exc
            final_keys = {
                _key(row["name"])
                for row in connection.execute(
                    """
                    SELECT c.name FROM product_categories AS pc
                    JOIN categories AS c ON c.id=pc.category_id WHERE pc.product_id=?
                    """,
                    (plan.product_id,),
                ).fetchall()
            }
            if final_keys != set(plan.live_keys):
                raise RuntimeError(f"{plan.code}: relaciones finales inesperadas; rollback.")  # noqa: TRY301
        result = str(connection.execute("PRAGMA integrity_check").fetchone()[0])
        if result != "ok":
            raise RuntimeError(f"integrity_check antes del commit: {result}")  # noqa: TRY301
        connection.commit()
        return plans, backup  # noqa: TRY300
    except Exception:
        if connection.in_transaction:
            connection.rollback()
        raise
    finally:
        connection.close()


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="backslashreplace")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, required=True, help="JSON de auditoría live.")
    parser.add_argument("--database", type=Path, help="DB auditada; por defecto, ruta del informe.")
    parser.add_argument("--codes", nargs="*", help="Códigos a revisar, por ejemplo FB-1908.")
    parser.add_argument("--apply", action="store_true", help="Aplicar; sin esta opción solo previsualiza.")
    args = parser.parse_args()
    try:
        report = load_report(args.report.expanduser().resolve())
        reported_database = Path(str(report["database"])).expanduser().resolve()
        database = args.database.expanduser().resolve() if args.database else reported_database
        if database != reported_database:
            raise ValueError("La DB indicada no coincide con la DB del informe.")  # noqa: TRY301
        if args.apply:
            plans, backup = apply_reported_repairs(database, report, args.codes)
        else:
            connection = _readonly_connection(database)
            try:
                result = str(connection.execute("PRAGMA integrity_check").fetchone()[0])
                if result != "ok":
                    raise ValueError(f"integrity_check: {result}")
                plans = build_repair_plans(connection, report, args.codes)
            finally:
                connection.close()
            backup = None

        print(
            "CATEGORY_MEMBERSHIP_RECONCILIATION|"
            f"mode={'APPLY' if args.apply else 'PREVIEW'}|database={database}|"
            f"targets={len(plans)}|changed={sum(plan.changed for plan in plans)}"
        )
        for plan in plans:
            print("CATEGORY_MEMBERSHIP_REPAIR_PLAN|" + json.dumps(plan.as_dict(), ensure_ascii=False))
        if backup:
            print(f"BACKUP_CREATED|{backup}")
        elif args.apply:
            print("NO_CHANGES_REQUIRED|true")
        changed = args.apply and any(plan.changed for plan in plans)
        print(
            "SAFETY|"
            f"database_rows_modified={str(changed).lower()}|"
            "product_stock_modified=False|images_modified=False|source_files_modified=False"
        )
        return 0  # noqa: TRY300
    except (OSError, sqlite3.Error, TypeError, ValueError, RuntimeError) as exc:
        parser.exit(2, f"ERROR|{exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
