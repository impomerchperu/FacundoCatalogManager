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
import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlsplit

from bs4 import BeautifulSoup

from config.runtime_paths import DATABASE_PATH
from database.db_manager import DBManager
from models.product import Product
from models.scraping.category import Category
from models.scraping.detail_description_policy import (
    has_technical_detail,
    is_complete_detail,
    is_valid_detail_content,
    normalize_detail_text,
)
from repositories.product_repository import ProductRepository
from scrapers.browser import Browser
from scrapers.collectors.product_collection_scraper import ProductCollectionScraper
from scrapers.collectors.resilient_category_scraper import ResilientCategoryScraper
from scrapers.extractors.category_extractor import CategoryExtractor
from scrapers.extractors.category_product_extractor import CategoryProductExtractor
from scrapers.extractors.product_card_extractor import ProductCardExtractor
from scrapers.extractors.product_extractor import ProductExtractor
from services.scraping.category_name_normalizer import (
    canonical_category_name,
    normalize_category_name,
    split_category_names,
)
from services.scraping.product_hash_service import ProductHashService
from services.scraping.scraping_config import ScrapingConfig

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
    product_override: Product | None = None,
    source_url_override: str | None = None,
) -> DetailRepairPlan:
    """Build one repair plan; never write product data."""
    if product_override is None:
        product, resolution_plan = _resolve_requested_product(
            repository,
            requested_code,
        )
        if resolution_plan is not None:
            return resolution_plan
        if product is None:
            raise RuntimeError("La resolución de producto no devolvió resultado.")
    else:
        product = product_override

    code = _normalize_code(product.code)
    url = (
        _source_product_url(db, code)
        if source_url_override is None
        else source_url_override
    )
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
            extractor.extract_authoritative_detail_text(
                soup,
                preserve_boundaries=True,
            )
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

    candidate = normalize_detail_text(
        authoritative_detail,
        preserve_boundaries=True,
    )
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
        if normalize_detail_text(
            current_description,
            preserve_boundaries=True,
        ) == candidate
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
    workers: int = 8,
    progress: Callable[[int, int, DetailRepairPlan], None] | None = None,
    products: list[Product] | None = None,
) -> dict[str, object]:
    """Compare selected catalog Details with source pages using bounded concurrency."""
    if workers < 1:
        raise ValueError("workers debe ser al menos 1.")

    selected_products = sorted(
        products if products is not None else repository.get_all(),
        key=lambda product: product.code.casefold(),
    )
    # Resolve URLs before starting HTTP workers: the shared SQLite connection and
    # repository stay on this thread; only in-memory products/URLs cross workers.
    products_and_urls = [
        (product, _source_product_url(db, product.code))
        for product in selected_products
    ]
    product_extractor = extractor or ProductExtractor()
    completed_plans: dict[str, DetailRepairPlan] = {}
    completed_count = 0

    with ThreadPoolExecutor(
        max_workers=workers,
        thread_name_prefix="detail-audit",
    ) as executor:
        futures = {
            executor.submit(
                _plan_single_product_detail_repair,
                db,
                repository,
                product.code,
                browser=browser,
                extractor=product_extractor,
                product_override=product,
                source_url_override=url,
            ): product
            for product, url in products_and_urls
        }
        for future in as_completed(futures):
            product = futures[future]
            plan = future.result()
            completed_plans[product.code] = plan
            completed_count += 1
            if progress is not None:
                progress(completed_count, len(selected_products), plan)

    plans = [completed_plans[product.code] for product in selected_products]
    counts = Counter(plan.status for plan in plans)
    comparable_statuses = {"unchanged", "would_update", "skip_invalid_detail"}
    compared = sum(counts[status] for status in comparable_statuses)
    return {
        "mode": "source_audit_only",
        "catalog_total": len(selected_products),
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

def _resolve_category_batches(
    repository: ProductRepository,
    requested_categories: list[str],
) -> list[tuple[str, list[Product]]]:
    """Resolve category names and deduplicated products for category-by-category repair."""
    products = sorted(
        repository.get_all(),
        key=lambda product: product.code.casefold(),
    )
    names_by_key: dict[str, str] = {}
    category_keys_by_code: dict[str, set[str]] = {}

    for product in products:
        code_key = product.code.casefold()
        category_keys: set[str] = set()
        for raw_name in split_category_names(product.category):
            name = canonical_category_name(raw_name)
            key = normalize_category_name(name)
            if not key:
                continue
            names_by_key.setdefault(key, name)
            category_keys.add(key)
        category_keys_by_code[code_key] = category_keys

    requested: list[tuple[str, str]] = []
    seen: set[str] = set()
    unknown: list[str] = []
    for raw_name in requested_categories:
        name = canonical_category_name(raw_name)
        key = normalize_category_name(name)
        if not key:
            continue
        if key not in names_by_key:
            unknown.append(str(raw_name))
            continue
        if key in seen:
            continue
        seen.add(key)
        requested.append((names_by_key[key], key))

    if unknown:
        raise ValueError(
            "No se encontraron estas categorías en products.category: "
            + ", ".join(unknown)
        )
    if not requested:
        raise ValueError("Debe indicarse al menos una categoría válida.")

    batches: list[tuple[str, list[Product]]] = []
    for name, key in requested:
        category_products = [
            product
            for product in products
            if key in category_keys_by_code.get(product.code.casefold(), set())
        ]
        if not category_products:
            raise ValueError(
                f"La categoría {name!r} no contiene productos en el catálogo."
            )
        batches.append((name, category_products))
    return batches


def _plans_from_audit_report(report: dict[str, object]) -> list[DetailRepairPlan]:
    """Rehydrate validated non-mutating audit rows for the transactional writer."""
    raw_items = report.get("items", [])
    if not isinstance(raw_items, list):
        return []
    plans: list[DetailRepairPlan] = []
    for raw_item in raw_items:
        if not isinstance(raw_item, dict):
            continue
        raw_product_id = raw_item.get("product_id")
        product_id = (
            int(raw_product_id)
            if isinstance(raw_product_id, int) and not isinstance(raw_product_id, bool)
            else None
        )
        plans.append(
            DetailRepairPlan(
                code=str(raw_item.get("code") or ""),
                status=str(raw_item.get("status") or ""),
                url=str(raw_item.get("url") or ""),
                old_description=str(raw_item.get("old_description") or ""),
                new_description=str(raw_item.get("new_description") or ""),
                reason=str(raw_item.get("reason") or ""),
                product_id=product_id,
            )
        )
    return plans


def _source_audit_summary(report: dict[str, object]) -> dict[str, object]:
    """Keep category progress reports compact while detailed records go to JSON."""
    keys = (
        "catalog_total",
        "source_fields_compared",
        "candidate_differences",
        "invalid_source_details",
        "fetch_errors",
        "products_without_source_url",
        "authoritative_detail_not_found",
        "status_counts",
    )
    return {key: report.get(key) for key in keys}


def _blocking_detail_codes(report: dict[str, object]) -> set[str]:
    """Collect products that could not be safely verified from the source field."""
    blocking_statuses = {
        "fetch_error",
        "skip_invalid_detail",
        "skip_source_url_not_found",
        "skip_authoritative_detail_not_found",
        "skip_code_mismatch",
        "skip_product_changed",
        "skip_card_product_not_found",
    }
    raw_items = report.get("items", [])
    if not isinstance(raw_items, list):
        return set()
    return {
        str(item.get("code") or "")
        for item in raw_items
        if isinstance(item, dict)
        and str(item.get("status") or "") in blocking_statuses
        and str(item.get("code") or "")
    }


def _card_detail_field_is_identified(card: Any, description: str) -> bool:
    """Tell an identified empty card Detail apart from a missing card field."""
    extractor = CategoryProductExtractor()
    if str(description or "").strip():
        return True
    # Use the same category-card extraction policy as the catalog scraper.
    # Empty .text-content shells must not override valid visible fallback text.
    if extractor._description(card).strip():
        return True

    authoritative = [
        element
        for element in card.select(".text-content")
        if not extractor._is_excluded_detail_block(element)
    ]
    if any(not element.get_text(" ", strip=True) for element in authoritative):
        # An explicitly empty, identified block is authoritative. A block that
        # contains only Color or generic text is not itself a valid Detail value.
        return True

    fallback_selectors = (".brxe-text", ".brxe-text-basic", "ul li", "ol li")
    return any(
        not extractor._is_excluded_detail_block(element)
        and bool(extractor._description_candidate(element))
        for element in card.select(", ".join(fallback_selectors))
    )


def _plan_from_detail_candidate(
    product: Product,
    url: str,
    candidate: str,
    *,
    reason: str,
) -> DetailRepairPlan:
    """Build a plan from an accepted Detail field without writing the database."""
    old_description = str(product.description or "")
    normalized_old = normalize_detail_text(old_description)
    normalized_candidate = normalize_detail_text(candidate)
    preserved_candidate = normalize_detail_text(
        candidate,
        preserve_boundaries=True,
    )
    return DetailRepairPlan(
        code=product.code,
        status=(
            "unchanged"
            if normalized_old == normalized_candidate
            else "would_update"
        ),
        url=url,
        product_id=product.product_id,
        old_description=old_description,
        new_description=preserved_candidate,
        reason=reason,
    )


def _plan_category_card_detail(
    db: DBManager,
    repository: ProductRepository,
    product: Product,
    card: Any,
    card_description: str,
    *,
    source_url: str,
    category_name: str,
    browser: Browser,
) -> DetailRepairPlan:
    """Use live category-card Detail first, supplementing only missing/incomplete values."""
    candidate = normalize_detail_text(
        card_description,
        preserve_boundaries=True,
    )
    if not candidate:
        # The collection scraper can leave source_product.description empty even
        # when the same card still exposes recoverable Detail in sibling blocks.
        # Re-extract from the raw card before interpreting it as authoritative
        # empty; otherwise _card_detail_field_is_identified may detect that
        # visible Detail exists while this planner still proposes clearing it.
        extracted_card_detail = CategoryProductExtractor()._description(card)
        candidate = normalize_detail_text(
            extracted_card_detail,
            preserve_boundaries=True,
        )
    field_identified = _card_detail_field_is_identified(card, candidate)

    if field_identified and not candidate:
        return _plan_from_detail_candidate(
            product,
            source_url,
            "",
            reason=(
                "El campo Detalle de la tarjeta está identificado y vacío; "
                "se conserva vacío y no se sustituye con la página individual."
            ),
        )

    if candidate and not _detail_issue(candidate):
        return _plan_from_detail_candidate(
            product,
            source_url,
            candidate,
            reason="Detalle obtenido del campo autorizado de la tarjeta de categoría.",
        )

    # Only a missing/unidentified or incomplete/truncated card value allows the
    # product-page field to supplement it. The single-product planner validates
    # page identity, authoritative field presence, and completeness before use.
    return _plan_single_product_detail_repair(
        db,
        repository,
        product.code,
        browser=browser,
        product_override=product,
        source_url_override=source_url,
        extractor=ProductExtractor(),
    )


def _audit_live_category_cards(  # noqa: PLR0912
    db: DBManager,
    repository: ProductRepository,
    category: Category,
    category_products: list[Product],
    *,
    browser: Browser,
    collection_scraper: ProductCollectionScraper,
) -> tuple[dict[str, object], bool]:
    """Compare one live category's card fields with its DB rows, without mutation."""
    raw_products = collection_scraper.collect_category(category)
    live_by_identity: dict[str, tuple[Any, str, Any]] = {}
    duplicate_live_codes: set[str] = set()
    unidentified_cards = 0

    for item in raw_products:
        if not isinstance(item, tuple) or len(item) != 3:
            unidentified_cards += 1
            continue
        card, _page_url, source_product = item
        code = _normalize_code(getattr(source_product, "code", ""))
        identity = _code_identity(code)
        if not identity:
            unidentified_cards += 1
            continue
        if identity in live_by_identity:
            duplicate_live_codes.add(code)
            continue
        live_by_identity[identity] = (card, str(getattr(source_product, "url", "") or ""), source_product)

    local_by_identity: dict[str, Product] = {}
    duplicate_local_codes: set[str] = set()
    for product in category_products:
        identity = _code_identity(product.code)
        if identity in local_by_identity:
            duplicate_local_codes.add(product.code)
            continue
        local_by_identity[identity] = product

    plans: list[DetailRepairPlan] = []
    missing_live_codes: list[str] = []
    for identity, product in local_by_identity.items():
        source = live_by_identity.get(identity)
        if source is None:
            missing_live_codes.append(product.code)
            plans.append(
                DetailRepairPlan(
                    code=product.code,
                    status="skip_card_product_not_found",
                    product_id=product.product_id,
                    old_description=str(product.description or ""),
                    reason=(
                        "El producto del catálogo local no se identificó por código "
                        "en las tarjetas actuales de esta categoría."
                    ),
                )
            )
            continue

        card, source_url, source_product = source
        plans.append(
            _plan_category_card_detail(
                db,
                repository,
                product,
                card,
                str(getattr(source_product, "description", "") or ""),
                source_url=source_url,
                category_name=category.name,
                browser=browser,
            )
        )

    coverage_issues: list[str] = []
    expected_count = max(int(getattr(category, "expected_count", 0) or 0), 0)
    if expected_count and len(raw_products) != expected_count:
        coverage_issues.append(
            f"El sitio publica {expected_count} productos, pero se extrajeron "
            f"{len(raw_products)} tarjetas únicas."
        )
    if missing_live_codes:
        coverage_issues.append(
            "No se encontraron en la categoría los códigos locales: "
            + ", ".join(sorted(missing_live_codes, key=str.casefold))
        )
    if duplicate_live_codes:
        coverage_issues.append(
            "Hay códigos duplicados en las tarjetas live: "
            + ", ".join(sorted(duplicate_live_codes, key=str.casefold))
        )
    if duplicate_local_codes:
        coverage_issues.append(
            "Hay códigos locales ambiguos: "
            + ", ".join(sorted(duplicate_local_codes, key=str.casefold))
        )
    if unidentified_cards:
        coverage_issues.append(
            f"{unidentified_cards} tarjetas no tienen un código identificable."
        )

    counts = Counter(plan.status for plan in plans)
    compared_statuses = {"unchanged", "would_update", "skip_invalid_detail"}
    report: dict[str, object] = {
        "mode": "category_card_source_audit",
        "catalog_total": len(category_products),
        "live_category_cards": len(raw_products),
        "source_fields_compared": sum(
            counts[status] for status in compared_statuses
        ),
        "candidate_differences": counts["would_update"],
        "invalid_source_details": counts["skip_invalid_detail"],
        "fetch_errors": counts["fetch_error"],
        "products_without_source_url": counts["skip_source_url_not_found"],
        "authoritative_detail_not_found": counts[
            "skip_authoritative_detail_not_found"
        ],
        "status_counts": dict(sorted(counts.items())),
        "coverage_verified": not coverage_issues,
        "coverage_issues": coverage_issues,
        "items": [asdict(plan) for plan in plans],
    }
    return report, not coverage_issues


def _repair_categories_by_batch(  # noqa: PLR0912
    db: DBManager,
    repository: ProductRepository,
    requested_categories: list[str],
    *,
    browser: Browser,
    workers: int,
    apply: bool,
) -> dict[str, object]:
    """Audit and repair category-card Detail values one category at a time."""
    batches = _resolve_category_batches(repository, requested_categories)
    backup_path = ""
    total_updated = 0
    total_fetch_errors = 0
    candidate_differences_remaining = 0
    unresolved_codes: set[str] = set()
    category_results: list[dict[str, object]] = []
    total_occurrences = sum(len(products) for _, products in batches)

    category_scraper = ResilientCategoryScraper(
        browser=browser,
        category_extractor=CategoryExtractor(),
    )
    collection_scraper = ProductCollectionScraper(
        category_scraper,
        ProductCardExtractor(),
        CategoryProductExtractor(),
        ProductExtractor(),
        max_workers=workers,
        category_page_workers=1,
    )
    try:
        live_categories = category_scraper.scrape(ScrapingConfig().catalog_url)
        live_categories_by_key = {
            normalize_category_name(getattr(item, "name", "")): item
            for item in live_categories or []
            if normalize_category_name(getattr(item, "name", ""))
        }
        if not live_categories_by_key:
            raise RuntimeError("No se pudieron descubrir las categorías live del catálogo.")

        print(
            f"[Detalle por categoría] {len(batches)} categorías; "
            f"{total_occurrences} productos locales en el ámbito.",
            file=sys.stderr,
            flush=True,
        )

        for category_name, category_products in batches:
            print(
                f"[Detalle por categoría] Iniciando: {category_name} "
                f"({len(category_products)} productos).",
                file=sys.stderr,
                flush=True,
            )
            live_category = live_categories_by_key.get(
                normalize_category_name(category_name)
            )
            if live_category is None:
                raise ValueError(
                    f"La categoría local {category_name!r} no se encontró en el "
                    "listado de categorías live; no se aplicarán cambios."
                )

            try:
                preview, coverage_verified = _audit_live_category_cards(
                    db,
                    repository,
                    live_category,
                    category_products,
                    browser=browser,
                    collection_scraper=collection_scraper,
                )
            except Exception as error:  # noqa: BLE001
                message = f"{type(error).__name__}: {error}"
                failed_plans = [
                    DetailRepairPlan(
                        code=product.code,
                        status="fetch_error",
                        product_id=product.product_id,
                        old_description=str(product.description or ""),
                        reason=message,
                    )
                    for product in category_products
                ]
                preview = {
                    "mode": "category_card_source_audit",
                    "catalog_total": len(category_products),
                    "live_category_cards": 0,
                    "source_fields_compared": 0,
                    "candidate_differences": 0,
                    "invalid_source_details": 0,
                    "fetch_errors": len(failed_plans),
                    "products_without_source_url": 0,
                    "authoritative_detail_not_found": 0,
                    "status_counts": {"fetch_error": len(failed_plans)},
                    "coverage_verified": False,
                    "coverage_issues": [message],
                    "items": [asdict(plan) for plan in failed_plans],
                }
                coverage_verified = False

            preview_summary = _source_audit_summary(preview)
            preview_summary["live_category_cards"] = preview.get("live_category_cards")
            preview_summary["coverage_verified"] = coverage_verified
            preview_summary["coverage_issues"] = preview.get("coverage_issues", [])
            preview_fetch_errors = int(preview.get("fetch_errors") or 0)
            total_fetch_errors += preview_fetch_errors
            unresolved_codes.update(_blocking_detail_codes(preview))
            if not coverage_verified:
                unresolved_codes.update(product.code for product in category_products)

            result: dict[str, object] = {
                "category": category_name,
                "products": len(category_products),
                "preview": preview_summary,
                "preview_items": preview.get("items", []),
                "updated": 0,
                "verification_runs": [],
                "coverage_verified": coverage_verified,
                "coverage_issues": preview.get("coverage_issues", []),
                "outcome": "preview_only",
            }

            if not apply:
                candidate_differences_remaining += int(
                    preview.get("candidate_differences") or 0
                )
                category_results.append(result)
                continue

            # Never write from an incomplete category scrape or from a category
            # whose product-card coverage/identity could not be reconciled.
            if preview_fetch_errors or not coverage_verified:
                result["outcome"] = (
                    "blocked_fetch_errors"
                    if preview_fetch_errors
                    else "blocked_category_coverage"
                )
                candidate_differences_remaining += int(
                    preview.get("candidate_differences") or 0
                )
                category_results.append(result)
                continue

            plans = _plans_from_audit_report(preview)
            proposed_updates = sum(plan.status == "would_update" for plan in plans)
            if proposed_updates and not backup_path:
                backup_path = str(_create_database_backup(db))

            updated = apply_detail_repairs(db, repository, plans)
            total_updated += updated
            result["updated"] = updated

            try:
                verification, verification_coverage = _audit_live_category_cards(
                    db,
                    repository,
                    live_category,
                    _resolve_category_batches(repository, [category_name])[0][1],
                    browser=browser,
                    collection_scraper=collection_scraper,
                )
            except Exception as error:  # noqa: BLE001
                verification = {
                    "candidate_differences": 0,
                    "fetch_errors": 1,
                    "items": [],
                    "coverage_issues": [f"{type(error).__name__}: {error}"],
                }
                verification_coverage = False
            total_fetch_errors += int(verification.get("fetch_errors") or 0)
            unresolved_codes.update(_blocking_detail_codes(verification))
            if not verification_coverage:
                unresolved_codes.update(product.code for product in category_products)

            verification_runs = result["verification_runs"]
            if isinstance(verification_runs, list):
                verification_runs.append(
                    {
                        "attempt": 1,
                        "summary": _source_audit_summary(verification),
                        "coverage_verified": verification_coverage,
                        "coverage_issues": verification.get("coverage_issues", []),
                        "items": verification.get("items", []),
                    }
                )

            remaining = int(verification.get("candidate_differences") or 0)
            if int(verification.get("fetch_errors") or 0) > 0:
                outcome = "verification_fetch_error"
                candidate_differences_remaining += remaining
            elif not verification_coverage:
                outcome = "verification_coverage_mismatch"
                candidate_differences_remaining += remaining
            elif remaining:
                outcome = "differences_remaining"
                candidate_differences_remaining += remaining
                unresolved_codes.update(
                    str(item.get("code") or "")
                    for item in verification.get("items", [])
                    if isinstance(item, dict)
                    and str(item.get("status") or "") == "would_update"
                    and str(item.get("code") or "")
                )
            else:
                outcome = (
                    "verified_with_skips"
                    if _blocking_detail_codes(verification)
                    else "verified"
                )
            result["outcome"] = outcome
            result["verification_summary"] = _source_audit_summary(verification)
            category_results.append(result)

    finally:
        collection_scraper.close()

    unique_product_codes = {
        product.code
        for _, products in batches
        for product in products
    }
    return {
        "mode": "category_apply_and_verify" if apply else "category_preview",
        "categories_requested": [name for name, _ in batches],
        "category_count": len(batches),
        "products_in_scope": len(unique_product_codes),
        "category_occurrences": total_occurrences,
        "database_backup": backup_path,
        "updated": total_updated,
        "fetch_errors": total_fetch_errors,
        "candidate_differences_remaining": candidate_differences_remaining,
        "unresolved_products": len(unresolved_codes),
        "unresolved_codes": sorted(unresolved_codes, key=str.casefold),
        "category_results": category_results,
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
    destination.write_text(serialized + "\n", encoding="utf-8")
    summary = {
        key: value
        for key, value in report.items()
        if key not in {"items", "category_results"}
    }
    summary["report_file"] = str(destination.resolve())
    summary["items_saved"] = len(items) if isinstance(items, list) else 0
    category_results = report.get("category_results")
    if isinstance(category_results, list):
        summary["category_results_saved"] = len(category_results)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


def _log_audit_progress(
    completed: int,
    total: int,
    plan: DetailRepairPlan,
) -> None:
    """Report coarse-grained progress without flooding the terminal."""
    if completed == 1 or completed % 10 == 0 or completed == total:
        percent = round(completed * 100 / max(total, 1))
        print(
            f"[Auditoría Detalle] {completed}/{total} ({percent}%) "
            f"| {plan.code}: {plan.status}",
            file=sys.stderr,
            flush=True,
        )


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


def main(argv: list[str] | None = None) -> int:  # noqa: PLR0912
    parser = argparse.ArgumentParser(
        description=(
            "Audita Detalle visible o repara códigos/categorías; nunca inicia un FULL."
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
        "--categories",
        nargs="+",
        metavar="CATEGORY",
        help=(
            "Previsualiza, aplica y audita productos por categoría, de una en una. "
            "El modo --apply hace respaldo y verifica cada categoría después de actualizar."
        ),
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
        "--audit-workers",
        type=int,
        default=8,
        help="Solicitudes simultáneas para auditorías por fuente/categoría (1 a 16; predeterminado: 8).",
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
    if not 1 <= args.audit_workers <= 16:
        parser.error("--audit-workers debe estar entre 1 y 16.")

    db = DBManager()
    browser: Browser | None = None
    exit_code = 0
    try:
        repository = ProductRepository(db)
        if args.audit_incomplete:
            report = audit_incomplete_details(db, repository, limit=args.limit)
            _emit_json_report(report, args.output)
        elif args.audit_source:
            browser = Browser(http_workers=args.audit_workers)
            browser.enable_thread_sessions()
            report = audit_source_details(
                db,
                repository,
                browser=browser,
                workers=args.audit_workers,
                progress=_log_audit_progress,
            )
            _emit_json_report(report, args.output)
            if report["fetch_errors"]:
                exit_code = 1
        elif args.categories:
            browser = Browser(http_workers=args.audit_workers)
            browser.enable_thread_sessions()
            report = _repair_categories_by_batch(
                db,
                repository,
                args.categories,
                browser=browser,
                workers=args.audit_workers,
                apply=args.apply,
            )
            _emit_json_report(report, args.output)
            if report["fetch_errors"]:
                exit_code = 1
            if args.apply and (
                report["unresolved_products"]
                or report["candidate_differences_remaining"]
            ):
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
