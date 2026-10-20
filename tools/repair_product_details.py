"""Repair technical Detail for selected catalog products without a full catalog sync.

Examples:
    python -m tools.repair_product_details --audit-incomplete
    python -m tools.repair_product_details --codes FB-1700 FB-6005 FB-6002 FB-1503
    python -m tools.repair_product_details --codes FB-1700 FB-6005 FB-6002 FB-1503 --apply

The default mode is a preview. Applying changes updates only products.description and
products.content_hash after validating the live page's product code and technical Detail.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any
from pathlib import Path
from urllib.parse import urlsplit

from bs4 import BeautifulSoup

from config.runtime_paths import DATABASE_PATH
from database.db_manager import DBManager
from models.scraping.detail_description_policy import (
    has_technical_detail,
    is_complete_detail,
    normalize_detail_text,
)
from repositories.product_repository import ProductRepository
from scrapers.browser import Browser
from scrapers.extractors.product_extractor import ProductExtractor
from services.scraping.product_hash_service import ProductHashService

_ALLOWED_HOSTS = frozenset({"stock.importacionesfacundo.com"})


@dataclass
class DetailRepairPlan:
    code: str
    status: str
    url: str = ""
    old_description: str = ""
    new_description: str = ""
    reason: str = ""
    product_id: int | None = None


def _normalize_code(value: object) -> str:
    return str(value or "").strip().upper()


def _is_allowed_source_url(value: object) -> bool:
    url = str(value or "").strip()
    try:
        parts = urlsplit(url)
    except ValueError:
        return False
    return (
        parts.scheme in {"http", "https"}
        and (parts.hostname or "").casefold() in _ALLOWED_HOSTS
    )


def _source_product_url(db: DBManager, code: str) -> str:
    """Resolve the latest known product URL without crawling any category."""
    queries = (
        "SELECT url AS product_url FROM scraped_products "
        "WHERE code=? COLLATE NOCASE AND TRIM(COALESCE(url, ''))<>'' "
        "ORDER BY rowid DESC LIMIT 1",
        "SELECT product_url FROM scraping_product_occurrences "
        "WHERE code=? COLLATE NOCASE AND TRIM(COALESCE(product_url, ''))<>'' "
        "ORDER BY rowid DESC LIMIT 1",
    )
    for query in queries:
        try:
            row = db.fetch_one(query, (code,))
        except sqlite3.OperationalError:
            continue
        if row is None:
            continue
        url = str(row["product_url"] or "").strip()
        if _is_allowed_source_url(url):
            return url
    return ""


def _detail_issue(value: object) -> str:
    description = normalize_detail_text(value)
    if not description:
        return "detalle_vacío"
    if not has_technical_detail(description):
        return "sin_atributos_técnicos_reconocibles"
    if not is_complete_detail(description):
        return "detalle_incompleto_o_truncado"
    return ""


def audit_incomplete_details(
    db: DBManager,
    repository: ProductRepository,
    *,
    limit: int = 100,
) -> dict[str, object]:
    """List local Detail values that fail the shared technical-detail policy."""
    findings: list[dict[str, object]] = []
    for product in sorted(repository.get_all(), key=lambda item: item.code.casefold()):
        reason = _detail_issue(product.description)
        if not reason:
            continue
        findings.append(
            {
                "code": product.code,
                "name": product.name,
                "reason": reason,
                "description": str(product.description or ""),
                "has_source_url": bool(_source_product_url(db, product.code)),
            }
        )
    safe_limit = max(int(limit), 1)
    return {
        "mode": "audit_only",
        "total_incomplete": len(findings),
        "returned": min(len(findings), safe_limit),
        "items": findings[:safe_limit],
    }


def plan_product_detail_repairs(
    db: DBManager,
    repository: ProductRepository,
    codes: list[str],
    *,
    browser: Any,
    extractor: ProductExtractor | None = None,
) -> list[DetailRepairPlan]:
    """Fetch only explicitly selected product pages and build a non-mutating plan."""
    product_extractor = extractor or ProductExtractor()
    plans: list[DetailRepairPlan] = []
    normalized_codes = list(dict.fromkeys(_normalize_code(code) for code in codes))
    normalized_codes = [code for code in normalized_codes if code]

    for code in normalized_codes:
        product = repository.get_by_code(code)
        if product is None:
            plans.append(
                DetailRepairPlan(
                    code=code,
                    status="skip_product_not_found",
                    reason="El código no existe en el catálogo local.",
                )
            )
            continue

        url = _source_product_url(db, code)
        if not url:
            plans.append(
                DetailRepairPlan(
                    code=code,
                    status="skip_source_url_not_found",
                    product_id=product.product_id,
                    old_description=str(product.description or ""),
                    reason="No hay una URL de origen válida guardada para este código.",
                )
            )
            continue

        try:
            html = browser.get(url)
            soup = BeautifulSoup(html, "lxml")
            scraped = product_extractor.extract(
                soup,
                url=url,
                category=product.category,
            )
        except Exception as error:  # noqa: BLE001
            plans.append(
                DetailRepairPlan(
                    code=code,
                    status="fetch_error",
                    url=url,
                    product_id=product.product_id,
                    old_description=str(product.description or ""),
                    reason=f"{type(error).__name__}: {error}",
                )
            )
            continue

        scraped_code = _normalize_code(getattr(scraped, "code", ""))
        if scraped_code != code:
            plans.append(
                DetailRepairPlan(
                    code=code,
                    status="skip_code_mismatch",
                    url=url,
                    product_id=product.product_id,
                    old_description=str(product.description or ""),
                    new_description=normalize_detail_text(
                        getattr(scraped, "description", "")
                    ),
                    reason=(
                        "El código extraído de la página no coincide "
                        f"(obtenido: {scraped_code or 'vacío'})."
                    ),
                )
            )
            continue

        candidate = normalize_detail_text(getattr(scraped, "description", ""))
        issue = _detail_issue(candidate)
        if issue:
            plans.append(
                DetailRepairPlan(
                    code=code,
                    status="skip_invalid_detail",
                    url=url,
                    product_id=product.product_id,
                    old_description=str(product.description or ""),
                    new_description=candidate,
                    reason=f"El detalle extraído no pasó la validación: {issue}.",
                )
            )
            continue

        current = str(product.description or "")
        if normalize_detail_text(current) == candidate:
            status = "unchanged"
        else:
            status = "would_update"
        plans.append(
            DetailRepairPlan(
                code=code,
                status=status,
                url=url,
                product_id=product.product_id,
                old_description=current,
                new_description=candidate,
            )
        )
    return plans


def apply_detail_repairs(
    db: DBManager,
    repository: ProductRepository,
    plans: list[DetailRepairPlan],
) -> int:
    """Commit only validated Detail text and the corresponding content hash."""
    candidates = [plan for plan in plans if plan.status == "would_update"]
    if not candidates:
        return 0

    db.begin()
    try:
        current_by_code = {}
        for plan in candidates:
            current = repository.get_by_code(plan.code)
            if (
                current is None
                or current.product_id != plan.product_id
                or str(current.description or "") != plan.old_description
            ):
                raise RuntimeError(
                    f"{plan.code}: el producto cambió durante la reparación; "
                    "se revirtieron todas las actualizaciones."
                )
            current_by_code[plan.code] = current

        hash_service = ProductHashService()
        for plan in candidates:
            current = current_by_code[plan.code]
            current.description = plan.new_description
            content_hash = hash_service.generate(current)
            db.execute_query(
                "UPDATE products SET description=?, content_hash=? WHERE id=?",
                (plan.new_description, content_hash, plan.product_id),
            )
            plan.status = "updated"
        db.commit()
    except Exception:
        db.rollback()
        raise
    return len(candidates)


def _create_database_backup(db: DBManager) -> Path:
    """Create a consistent SQLite backup before any catalog row is modified."""
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
    backup_path = Path(DATABASE_PATH).with_name(
        f"{Path(DATABASE_PATH).stem}.before_detail_repair_{timestamp}"
        f"{Path(DATABASE_PATH).suffix}"
    )
    with sqlite3.connect(str(backup_path)) as destination:
        db.connection.backup(destination)
    return backup_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Audita Detalle o repara códigos específicos; nunca inicia un FULL."
        )
    )
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument(
        "--codes",
        nargs="+",
        metavar="CODE",
        help="Códigos exactos que se deben revisar (las páginas se consultan individualmente).",
    )
    selection.add_argument(
        "--audit-incomplete",
        action="store_true",
        help="Lista detalles locales incompletos sin hacer solicitudes web ni escribir productos.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Aplica los detalles válidos; por defecto solo muestra una vista previa.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=100,
        help="Máximo de filas que se muestran en la auditoría local (predeterminado: 100).",
    )
    args = parser.parse_args(argv)
    if args.apply and args.audit_incomplete:
        parser.error("--apply no se puede usar con --audit-incomplete.")
    if args.limit < 1:
        parser.error("--limit debe ser al menos 1.")

    db = DBManager()
    browser: Browser | None = None
    try:
        repository = ProductRepository(db)
        if args.audit_incomplete:
            print(
                json.dumps(
                    audit_incomplete_details(db, repository, limit=args.limit),
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return 0

        browser = Browser(http_workers=1)
        plans = plan_product_detail_repairs(
            db,
            repository,
            args.codes or [],
            browser=browser,
        )
        backup_path = ""
        applied = 0
        if args.apply and any(plan.status == "would_update" for plan in plans):
            backup_path = str(_create_database_backup(db))
            applied = apply_detail_repairs(db, repository, plans)

        print(
            json.dumps(
                {
                    "mode": "apply" if args.apply else "preview",
                    "database_backup": backup_path,
                    "updated": applied,
                    "items": [asdict(plan) for plan in plans],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        if any(plan.status == "fetch_error" for plan in plans):
            return 1
        return 0
    except Exception as error:  # noqa: BLE001
        print(f"Error: {type(error).__name__}: {error}", file=sys.stderr)
        return 2
    finally:
        if browser is not None:
            browser.close()
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
