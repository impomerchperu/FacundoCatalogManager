"""Audit live category listings against saved category-product relations.

Run from the repository root:
    python tools/audit_category_memberships_live_readonly.py
    python tools/audit_category_memberships_live_readonly.py --codes FB-1908 FB-4047

This audit requests category listing pages only. It does not open product detail
pages, update SQLite, synchronize products, or modify local images.
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config.runtime_paths import DATABASE_PATH
from config.scraping_config import (
    MAX_RETRIES,
    REQUEST_TIMEOUT,
    SCRAPING_CATEGORY_PAGE_WORKERS,
    SCRAPING_CATEGORY_WORKERS,
    SCRAPING_HTTP_WORKERS,
    SCRAPING_JSF_HTTP_CONCURRENCY,
    SCRAPING_JSF_PAGE_WORKERS,
    SCRAPING_MAX_WORKERS,
    STORE_URL,
)
from scrapers.browser import Browser
from scrapers.collectors.product_collection_scraper import ProductCollectionScraper
from scrapers.collectors.resilient_category_scraper import ResilientCategoryScraper
from scrapers.extractors.category_extractor import CategoryExtractor
from scrapers.extractors.category_product_extractor import CategoryProductExtractor
from scrapers.extractors.product_card_extractor import ProductCardExtractor
from scrapers.extractors.product_extractor import ProductExtractor
from services.scraping.category_name_normalizer import normalize_category_name
from services.scraping.category_service import CategoryService

TEMP = Path(os.environ.get("TEMP", str(Path.home())))
EXPECTED_CATEGORIES = 24
DEFAULT_CODES = ("FB-1908", "FB-4047", "FB-4048", "FB-3024", "TPSTCB")


def _normalize_code(value: object) -> str:
    return str(value or "").strip().upper()


def _readonly_connection(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA query_only = ON")
    return connection


def read_database_memberships(
    database_path: Path,
    codes: tuple[str, ...] | list[str],
) -> tuple[str, dict[str, dict[str, Any]]]:
    """Read product-category memberships from an existing SQLite DB."""
    connection = _readonly_connection(database_path)
    try:
        integrity = str(connection.execute("PRAGMA integrity_check").fetchone()[0])
        tables = {
            str(row[0])
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        result = {
            _normalize_code(code): {
                "code": _normalize_code(code),
                "product_found": False,
                "name": "",
                "categories": [],
            }
            for code in codes
        }
        if not {"products", "categories", "product_categories"}.issubset(tables):
            raise sqlite3.OperationalError(
                "La base requiere products, categories y product_categories."
            )
        selected = tuple(result)
        if not selected:
            return integrity, result
        placeholders = ",".join("?" for _ in selected)
        rows = connection.execute(
            f"""
            SELECT p.code, p.name, c.name AS category_name, c.canonical_url
            FROM products AS p
            LEFT JOIN product_categories AS pc ON pc.product_id = p.id
            LEFT JOIN categories AS c ON c.id = pc.category_id
            WHERE UPPER(TRIM(p.code)) IN ({placeholders})
            ORDER BY p.code COLLATE NOCASE, c.name COLLATE NOCASE
            """,
            selected,
        ).fetchall()
        for row in rows:
            code = _normalize_code(row["code"])
            target = result.get(code)
            if target is None:
                continue
            target["product_found"] = True
            target["name"] = str(row["name"] or "")
            category_name = str(row["category_name"] or "").strip()
            if category_name:
                target["categories"].append(category_name)
        for target in result.values():
            target["categories"] = sorted(
                set(target["categories"]), key=str.casefold
            )
        return integrity, result
    finally:
        connection.close()


def build_target_results(
    codes: tuple[str, ...] | list[str],
    database_memberships: dict[str, dict[str, Any]],
    live_memberships: dict[str, set[str]],
    *,
    coverage_complete: bool,
) -> list[dict[str, Any]]:
    """Compare selected relation sets and keep incomplete audits inconclusive."""
    results: list[dict[str, Any]] = []
    for raw_code in codes:
        code = _normalize_code(raw_code)
        database_row = database_memberships.get(code, {})
        database_categories = list(database_row.get("categories", []))
        live_categories = sorted(
            live_memberships.get(code, set()),
            key=str.casefold,
        )
        db_keys = {normalize_category_name(item): item for item in database_categories}
        live_keys = {normalize_category_name(item): item for item in live_categories}
        db_only = [
            db_keys[key] for key in sorted(set(db_keys) - set(live_keys))
        ]
        live_only = [
            live_keys[key] for key in sorted(set(live_keys) - set(db_keys))
        ]
        results.append(
            {
                "code": code,
                "name": str(database_row.get("name", "") or ""),
                "product_found_in_database": bool(database_row.get("product_found")),
                "database_categories": database_categories,
                "live_listing_categories": live_categories,
                "database_relations_not_seen_live": db_only,
                "live_relations_missing_from_database": live_only,
                "coverage_complete": bool(coverage_complete),
                "decision": (
                    "REVIEW_ONLY_COVERAGE_VERIFIED"
                    if coverage_complete
                    else "INCONCLUSIVE_INCOMPLETE_LIVE_COVERAGE"
                ),
            }
        )
    return results


def _collect_live_category_memberships(
    codes: tuple[str, ...] | list[str],
) -> tuple[dict[str, set[str]], dict[str, Any]]:
    """Collect card listings only; do not request product-detail pages."""
    targets = {_normalize_code(code) for code in codes}
    browser = Browser(
        request_timeout=REQUEST_TIMEOUT,
        max_retries=MAX_RETRIES,
        http_workers=SCRAPING_HTTP_WORKERS,
    )
    browser.enable_thread_sessions()
    category_scraper = ResilientCategoryScraper(
        browser=browser,
        category_extractor=CategoryExtractor(),
        jsf_http_concurrency=SCRAPING_JSF_HTTP_CONCURRENCY,
        jsf_page_workers=SCRAPING_JSF_PAGE_WORKERS,
    )
    collection = ProductCollectionScraper(
        category_scraper,
        ProductCardExtractor(),
        CategoryProductExtractor(),
        ProductExtractor(),
        max_workers=SCRAPING_MAX_WORKERS,
        category_page_workers=SCRAPING_CATEGORY_PAGE_WORKERS,
    )

    live_memberships: dict[str, set[str]] = defaultdict(set)
    categories_report: list[dict[str, Any]] = []
    missing_code_cards: list[dict[str, str]] = []
    total_expected_occurrences = 0
    total_cards = 0
    category_count_gap = False
    try:
        categories = list(CategoryService(category_scraper, STORE_URL).scrape_all() or [])
        if len(categories) != EXPECTED_CATEGORIES:
            raise RuntimeError(
                f"Se esperaban {EXPECTED_CATEGORIES} categorías; "
                f"se encontraron {len(categories)}."
            )

        category_workers = min(SCRAPING_CATEGORY_WORKERS, len(categories))
        # Listing requests are parallelized across categories; no enrichment executor
        # is submitted, so this audit does not fetch product detail pages.
        from concurrent.futures import ThreadPoolExecutor, as_completed

        collected_by_index: list[list[Any] | None] = [None] * len(categories)
        with ThreadPoolExecutor(max_workers=category_workers) as executor:
            futures = {
                executor.submit(collection.collect_category, category): index
                for index, category in enumerate(categories)
            }
            for future in as_completed(futures):
                collected_by_index[futures[future]] = future.result()

        for index, category in enumerate(categories):
            category_name = str(getattr(category, "name", "") or "").strip()
            category_key = normalize_category_name(category_name)
            expected = max(int(getattr(category, "expected_count", 0) or 0), 0)
            raw_items = collected_by_index[index] or []
            found = len(raw_items)
            total_expected_occurrences += expected
            total_cards += found
            if found != expected:
                category_count_gap = True

            target_hits = 0
            category_missing_code_count = 0
            for item in raw_items:
                product = item[2] if isinstance(item, tuple) and len(item) >= 3 else item
                code = _normalize_code(getattr(product, "code", ""))
                name = str(getattr(product, "name", "") or "").strip()
                url = str(getattr(product, "url", "") or "").strip()
                if not code:
                    category_missing_code_count += 1
                    missing_code_occurrence_count += 1
                    if name or url:
                        missing_code_cards.append(
                            {
                                "category": category_name,
                                "name": name,
                                "url": url,
                            }
                        )
                    continue
                if code in targets and category_key:
                    live_memberships[code].add(category_name)
                    target_hits += 1

            categories_report.append(
                {
                    "category": category_name,
                    "expected_occurrences": expected,
                    "collected_cards": found,
                    "target_hits": target_hits,
                    "cards_without_code": category_missing_code_count,
                    "count_matches": found == expected,
                }
            )

        coverage_complete = (
            not category_count_gap
            and missing_code_occurrence_count == 0
            and len(categories) == EXPECTED_CATEGORIES
        )
        metrics = {
            "categories_expected": EXPECTED_CATEGORIES,
            "categories_found": len(categories),
            "expected_category_occurrences": total_expected_occurrences,
            "collected_category_cards": total_cards,
            "category_count_gaps": category_count_gap,
            "missing_code_card_count": missing_code_occurrence_count,
            "missing_code_card_samples": missing_code_cards[:50],
            "coverage_complete": coverage_complete,
            "categories": categories_report,
        }
        return dict(live_memberships), metrics
    finally:
        collection.close()


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="backslashreplace")

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--database",
        type=Path,
        default=DATABASE_PATH,
        help=f"Base SQLite existente a leer (predeterminado: {DATABASE_PATH}).",
    )
    parser.add_argument(
        "--codes",
        nargs="*",
        default=list(DEFAULT_CODES),
        help="Códigos que se comprobarán; por defecto usa los candidatos actuales.",
    )
    args = parser.parse_args()
    database_path = args.database.expanduser().resolve()
    if not database_path.is_file():
        raise SystemExit(f"No existe la base indicada: {database_path}")

    codes = tuple(dict.fromkeys(_normalize_code(code) for code in args.codes))
    integrity, database_memberships = read_database_memberships(database_path, codes)
    live_memberships, live_metrics = _collect_live_category_memberships(codes)
    results = build_target_results(
        codes,
        database_memberships,
        live_memberships,
        coverage_complete=bool(live_metrics["coverage_complete"]),
    )
    report = {
        "report_type": "FCM_LIVE_CATEGORY_MEMBERSHIP_AUDIT_READ_ONLY",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "database": str(database_path),
        "integrity": integrity,
        "database_memberships": database_memberships,
        "live_metrics": live_metrics,
        "target_results": results,
        "safety": {
            "database_opened_read_only": True,
            "database_rows_modified": False,
            "product_detail_pages_requested": False,
            "images_or_source_files_modified": False,
            "automatic_repairs_performed": False,
        },
    }
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    report_path = TEMP / f"fcm_live_category_membership_audit_{stamp}.json"
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, default=str) + "\n",
        encoding="utf-8",
    )

    print(
        "LIVE_CATEGORY_MEMBERSHIP_AUDIT|"
        f"integrity={integrity}|"
        f"categories={live_metrics['categories_found']}/"
        f"{live_metrics['categories_expected']}|"
        f"expected_occurrences={live_metrics['expected_category_occurrences']}|"
        f"cards={live_metrics['collected_category_cards']}|"
        f"coverage_complete={live_metrics['coverage_complete']}|"
        f"cards_without_code={live_metrics['missing_code_card_count']}"
    )
    for item in results:
        print("TARGET_CATEGORY_MEMBERSHIP|" + json.dumps(item, ensure_ascii=False, separators=(",", ":")))
    for category in live_metrics["categories"]:
        if not category["count_matches"] or category["cards_without_code"]:
            print("CATEGORY_COVERAGE_GAP|" + json.dumps(category, ensure_ascii=False, separators=(",", ":")))
    if live_metrics["missing_code_card_samples"]:
        print(
            "MISSING_CODE_CARD_SAMPLES|"
            + json.dumps(
                live_metrics["missing_code_card_samples"],
                ensure_ascii=False,
                separators=(",", ":"),
            )
        )
    print(f"REPORT_JSON|{report_path}")
    print(
        "NO_DATABASE_OR_SOURCE_FILE_MODIFICATIONS|"
        "database_rows_modified=False|product_detail_pages_requested=False"
    )
    return 0 if integrity == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
