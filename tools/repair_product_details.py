"""Repair technical Detail for selected catalog products without a full catalog sync.

Examples:
    python -m tools.repair_product_details --audit-incomplete
    python -m tools.repair_product_details --codes FB-1700 FB-6005 FB-6002 FB-1503
    python -m tools.repair_product_details --codes FB-1700 FB-6005 FB-6002 FB-1503 --apply

The default mode is a preview. Applying changes updates only products.description and
products.content_hash after validating the live page's product code and visible Detail content.
"""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
from collections import Counter
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from bs4 import BeautifulSoup

from config.runtime_paths import DATABASE_PATH
from database.db_manager import DBManager
from models.product import Product
from models.scraping.detail_description_policy import (
    has_technical_detail,
    is_complete_detail,
    is_valid_detail_content,
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


def _code_identity(value: object) -> str:
    """Compare SKU forms such as FB2043 and FB-2043 without dropping identity."""
    return re.sub(r"[\s-]+", "", _normalize_code(value))


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
    if has_technical_detail(description):
        if not is_complete_detail(description):
            return "detalle_incompleto_o_truncado"
        return ""
    if is_valid_detail_content(description):
        return ""
    return "sin_detalle_visible_válido"


def audit_incomplete_details(
    db: DBManager,
    repository: ProductRepository,
    *,
    limit: int = 100,
) -> dict[str, object]:
    """List local Detail values that fail the visible-summary policy."""
    findings: list[dict[str, object]] = []
    for product in sorted(repository.get_all(), key=lambda item: item.code.casefold()):
        # Un Detalle vacío puede ser correcto si el campo de origen está vacío.
        # Por sí solo no constituye un defecto que deba repararse.
        if not str(product.description or "").strip():
            continue
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


def _resolve_requested_product(
    repository: ProductRepository,
    requested_code: str,
) -> tuple[Product | None, DetailRepairPlan | None]:
    """Resolve a requested SKU without guessing when its normalized form is ambiguous."""
    product = repository.get_by_code(requested_code)
    if product is not None:
        return product, None

    identity = _code_identity(requested_code)
    equivalent = [
        candidate
        for candidate in repository.get_all()
        if _code_identity(candidate.code) == identity
    ]
    if len(equivalent) == 1:
        return equivalent[0], None
    if len(equivalent) > 1:
        return None, DetailRepairPlan(
            code=requested_code,
            status="skip_ambiguous_product_code",
            reason=(
                "El código sin separadores coincide con varios "
                "productos del catálogo; no se modificó ninguno."
            ),
        )
    return None, DetailRepairPlan(
        code=requested_code,
        status="skip_product_not_found",
        reason="El código no existe en el catálogo local.",
    )


def _plan_single_product_detail_repair(
    db: DBManager,
    repository: ProductRepository,
    requested_code: str,
    *,
    browser: Any,
    extractor: ProductExtractor,
) -> DetailRepairPlan:
    """Build one repair plan; never write product data."""
    product, resolution_plan = _resolve_requested_product(
        repository,
        requested_code,
    )
    if resolution_plan is not None:
        return resolution_plan
    if product is None:
        raise RuntimeError("La resolución de producto no devolvió resultado.")

    code = _normalize_code(product.code)
    url = _source_product_url(db, code)
    if not url:
        return DetailRepairPlan(
            code=code,
            status="skip_source_url_not_found",
            product_id=product.product_id,
            old_description=str(product.description or ""),
            reason="No hay una URL de origen válida guardada para este código.",
        )

    try:
        html = browser.get(url)
        soup = BeautifulSoup(html, "lxml")
        detail_field_found, authoritative_detail = (
            extractor.extract_authoritative_detail_text(soup)
        )
        scraped = extractor.extract(
            soup,
            url=url,
            category=product.category,
        )
    except Exception as error:  # noqa: BLE001
        return DetailRepairPlan(
            code=code,
            status="fetch_error",
            url=url,
            product_id=product.product_id,
            old_description=str(product.description or ""),
            reason=f"{type(error).__name__}: {error}",
        )

    scraped_code = _normalize_code(getattr(scraped, "code", ""))
    current_description = str(product.description or "")
    if _code_identity(scraped_code) != _code_identity(code):
        return DetailRepairPlan(
            code=code,
            status="skip_code_mismatch",
            url=url,
            product_id=product.product_id,
            old_description=current_description,
            new_description=normalize_detail_text(
                getattr(scraped, "description", "")
            ),
            reason=(
                "El código extraído de la página no coincide "
                f"(obtenido: {scraped_code or 'vacío'})."
            ),
        )

    if not detail_field_found:
        return DetailRepairPlan(
            code=code,
            status="skip_authoritative_detail_not_found",
            url=url,
            product_id=product.product_id,
            old_description=current_description,
            new_description=normalize_detail_text(
                getattr(scraped, "description", "")
            ),
            reason=(
                "No se identificó el campo autorizado Detalle en la página; "
                "se omitió la reparación para no tomar contenido alternativo."
            ),
        )

    candidate = normalize_detail_text(authoritative_detail)
    issue = _detail_issue(candidate) if candidate else ""
    if issue:
        return DetailRepairPlan(
            code=code,
            status="skip_invalid_detail",
            url=url,
            product_id=product.product_id,
            old_description=current_description,
            new_description=candidate,
            reason=f"El detalle extraído no pasó la validación: {issue}.",
        )

    status = (
        "unchanged"
        if normalize_detail_text(current_description) == candidate
        else "would_update"
    )
    return DetailRepairPlan(
        code=code,
        status=status,
        url=url,
        product_id=product.product_id,
        old_description=current_description,
        new_description=candidate,
    )


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
    normalized_codes: list[str] = []
    seen_code_identities: set[str] = set()
    for raw_code in codes:
        code = _normalize_code(raw_code)
        identity = _code_identity(code)
        if code and identity and identity not in seen_code_identities:
            normalized_codes.append(code)
            seen_code_identities.add(identity)

    return [
        _plan_single_product_detail_repair(
            db,
            repository,
            requested_code,
            browser=browser,
            extractor=product_extractor,
        )
        for requested_code in normalized_codes
    ]


def audit_source_details(
    db: DBManager,
    repository: ProductRepository,
    *,
    browser: Any,
    extractor: ProductExtractor | None = None,
) -> dict[str, object]:
    """Compare every catalog Detail against its authoritative live product page."""
    products = sorted(
        repository.get_all(),
        key=lambda product: product.code.casefold(),
    )
    plans = plan_product_detail_repairs(
        db,
        repository,
        [product.code for product in products],
        browser=browser,
        extractor=extractor,
    )
    counts = Counter(plan.status for plan in plans)
    comparable_statuses = {"unchanged", "would_update", "skip_invalid_detail"}
    compared = sum(counts[status] for status in comparable_statuses)
    return {
        "mode": "source_audit_only",
        "catalog_total": len(products),
        "plans_returned": len(plans),
        "source_fields_compared": compared,
        "candidate_differences": counts["would_update"],
        "invalid_source_details": counts["skip_invalid_detail"],
        "fetch_errors": counts["fetch_error"],
        "products_without_source_url": counts["skip_source_url_not_found"],
        "authoritative_detail_not_found": counts[
            "skip_authoritative_detail_not_found"
        ],
        "status_counts": dict(sorted(counts.items())),
        "items": [asdict(plan) for plan in plans],
    }


def _emit_json_report(
    report: dict[str, object],
    output_path: Path | None,
) -> None:
    """Print a report or write full records to UTF-8 and print only its summary."""
    serialized = json.dumps(report, ensure_ascii=False, indent=2)
    items = report.get("items", [])
    if output_path is None:
        print(serialized)
        return

    destination = output_path.expanduser()
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(serialized + "\\n", encoding="utf-8")
    summary = {key: value for key, value in report.items() if key != "items"}
    summary["report_file"] = str(destination.resolve())
    summary["items_saved"] = len(items) if isinstance(items, list) else 0
    print(json.dumps(summary, ensure_ascii=False, indent=2))


def _get_unchanged_product(
    repository: ProductRepository,
    plan: DetailRepairPlan,
) -> Product:
    """Return the planned product only if its identity and Detail are unchanged."""
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
    return current


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
        current_by_code: dict[str, Product] = {}
        for plan in candidates:
            current_by_code[plan.code] = _get_unchanged_product(
                repository,
                plan,
            )

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
    destination = sqlite3.connect(str(backup_path))
    try:
        db.connection.backup(destination)
    finally:
        destination.close()
    return backup_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Audita Detalle visible o repara códigos específicos; nunca inicia un FULL."
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
    selection.add_argument(
        "--audit-source",
        action="store_true",
        help="Compara el Detalle de todos los productos con su página de origen; es solo lectura.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Guarda el JSON completo en un archivo UTF-8 y muestra un resumen en consola.",
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
    if args.apply and (args.audit_incomplete or args.audit_source):
        parser.error("--apply no se puede usar con los modos de auditoría.")
    if args.limit < 1:
        parser.error("--limit debe ser al menos 1.")

    db = DBManager()
    browser: Browser | None = None
    exit_code = 0
    try:
        repository = ProductRepository(db)
        if args.audit_incomplete:
            report = audit_incomplete_details(db, repository, limit=args.limit)
            _emit_json_report(report, args.output)
        elif args.audit_source:
            browser = Browser(http_workers=1)
            report = audit_source_details(
                db,
                repository,
                browser=browser,
            )
            _emit_json_report(report, args.output)
            if report["fetch_errors"]:
                exit_code = 1
        else:
            browser = Browser(http_workers=1)
            plans = plan_product_detail_repairs(
                db,
                repository,
                args.codes or [],
                browser=browser,
            )
            backup_path = ""
            applied = 0
            if args.apply and any(
                plan.status == "would_update" for plan in plans
            ):
                backup_path = str(_create_database_backup(db))
                applied = apply_detail_repairs(db, repository, plans)

            report = {
                "mode": "apply" if args.apply else "preview",
                "database_backup": backup_path,
                "updated": applied,
                "items": [asdict(plan) for plan in plans],
            }
            _emit_json_report(report, args.output)
            if any(plan.status == "fetch_error" for plan in plans):
                exit_code = 1
    except Exception as error:  # noqa: BLE001
        print(f"Error: {type(error).__name__}: {error}", file=sys.stderr)
        exit_code = 2
    finally:
        if browser is not None:
            browser.close()
        db.close()
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
