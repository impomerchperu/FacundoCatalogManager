"""Recover missing product SKUs from authoritative WooCommerce detail pages."""

from __future__ import annotations

import requests
from bs4 import BeautifulSoup

from scrapers.extractors.product_extractor import ProductExtractor
from services.scraping.category_name_normalizer import (
    canonical_category_name,
    normalize_category_name,
    split_category_names,
)
from services.scraping.category_product_sync_service import (
    CategoryProductSyncService,
)

_PATCHED = False
_ORIGINAL_FULL_SYNC_PRUNE_GUARD = (
    CategoryProductSyncService._full_sync_prune_guard
)
_ORIGINAL_ATTACH_CATEGORY_COVERAGE = (
    CategoryProductSyncService._attach_category_coverage
)


def _browser_for_service(service):
    scraper = getattr(getattr(service, "scraper_service", None), "scraper", None)
    if scraper is None:
        return None
    browser = getattr(scraper, "browser", None)
    if browser is not None:
        return browser
    category_scraper = getattr(scraper, "category_scraper", None)
    return getattr(category_scraper, "browser", None)


def _recover_one(product, browser, extractor: ProductExtractor) -> bool:
    code = str(getattr(product, "code", "") or "").strip()
    if code:
        return False

    url = str(getattr(product, "url", "") or "").strip()
    if "/producto/" not in url:
        return False

    try:
        html = browser.get(url)
    except requests.RequestException:
        return False

    if not isinstance(html, str) or not html:
        return False

    soup = BeautifulSoup(html, "lxml")
    recovered_code = str(extractor.extract_code(soup) or "").strip()
    if not recovered_code:
        return False

    product.code = recovered_code.upper()
    return True


def _recover_missing_codes(self, products) -> int:
    browser = _browser_for_service(self)
    if browser is None:
        return 0

    missing_products = [
        product
        for product in products
        if not str(getattr(product, "code", "") or "").strip()
        and "/producto/" in str(getattr(product, "url", "") or "")
    ]
    if not missing_products:
        return 0

    extractor = ProductExtractor()
    recovered = 0
    for product in missing_products:
        if _recover_one(product, browser, extractor):
            recovered += 1
    return recovered


def _full_sync_prune_guard(
    self,
    products,
    category_count,
    expected_category_occurrences=0,
    expected_products=None,
):
    _recover_missing_codes(self, products)

    if not products:
        return False, "no_products"
    if category_count <= 0:
        return False, "no_categories"

    expected_occurrences = max(int(expected_category_occurrences or 0), 0)
    if expected_occurrences <= 0:
        return False, "no_expected_category_occurrences"

    missing = sum(
        1
        for product in products
        if not str(getattr(product, "code", "") or "").strip()
    )
    if missing:
        return False, f"missing_codes:{missing}"

    browser = _browser_for_service(self)
    getter = getattr(browser, "get_http_metrics", None)
    if callable(getter):
        metrics = getter() or {}
        errors = int(metrics.get("http_terminal_errors", 0) or 0)
        if errors:
            return False, f"terminal_http_errors:{errors}"

    expected_unique = max(int(expected_products or 0), 0)
    if expected_unique > 0:
        unique_codes = {
            str(getattr(product, "code", "")).strip().casefold()
            for product in products
            if str(getattr(product, "code", "")).strip()
        }
        if len(unique_codes) < expected_unique:
            return False, f"unique_coverage_gap:{expected_unique - len(unique_codes)}"

    category_summary = getattr(self.last_sync_result, "category_summary", [])
    for row in category_summary:
        expected = max(int(row.get("expected", 0) or 0), 0)
        if expected <= 0:
            continue
        products_found = int(row.get("products", 0) or 0)
        unique_found = int(row.get("unique_products", 0) or 0)
        if products_found != expected or unique_found != expected:
            return (
                False,
                f"category_coverage_gap:{row.get('category', '')}",
            )

    if len(products) < expected_occurrences:
        return False, f"category_coverage_gap:{expected_occurrences - len(products)}"

    return _ORIGINAL_FULL_SYNC_PRUNE_GUARD(
        products,
        category_count,
        expected_category_occurrences=expected_occurrences,
        expected_products=expected_unique,
    )


def _attach_category_coverage(self, raw_products, products, categories):
    _ORIGINAL_ATTACH_CATEGORY_COVERAGE(self, raw_products, products, categories)

    by_code = {}
    for product in raw_products or []:
        code = str(getattr(product, "code", "") or "").strip()
        if code:
            by_code.setdefault(code.casefold(), []).append(product)

    multiple = []
    for code, occurrences in by_code.items():
        category_keys = set()
        category_names = []
        for product in occurrences:
            for category_name in split_category_names(
                getattr(product, "category", "")
            ):
                normalized = normalize_category_name(category_name)
                if not normalized or normalized in category_keys:
                    continue
                category_keys.add(normalized)
                display_name = canonical_category_name(category_name)
                if display_name and display_name not in category_names:
                    category_names.append(display_name)
        if len(category_keys) > 1:
            multiple.append(
                {
                    "code": str(getattr(occurrences[0], "code", code)).strip(),
                    "name": str(getattr(occurrences[0], "name", "")).strip(),
                    "categories": category_names,
                }
            )

    self.last_sync_result.multiple_category_products = multiple
    self.last_sync_result.products_multiple_categories = len(multiple)


def activate() -> None:
    """Install authoritative detail-page SKU recovery once."""
    global _PATCHED
    if _PATCHED:
        return
    CategoryProductSyncService._full_sync_prune_guard = _full_sync_prune_guard
    CategoryProductSyncService._attach_category_coverage = _attach_category_coverage
    _PATCHED = True


activate()

__all__ = ["activate"]
