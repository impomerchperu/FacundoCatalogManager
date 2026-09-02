"""Recover missing product SKUs from authoritative WooCommerce detail pages."""

from __future__ import annotations

from bs4 import BeautifulSoup

from scrapers.extractors.product_extractor import ProductExtractor
from services.scraping.category_product_sync_service import (
    CategoryProductSyncService,
)

_PATCHED = False
_ORIGINAL_FULL_SYNC_PRUNE_GUARD = (
    CategoryProductSyncService._full_sync_prune_guard
)


def _recover_one(product, browser, extractor: ProductExtractor) -> bool:
    code = str(getattr(product, "code", "") or "").strip()
    if code:
        return False

    url = str(getattr(product, "url", "") or "").strip()
    if "/producto/" not in url:
        return False

    try:
        html = browser.get(url)
    except Exception:
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
    browser = getattr(self, "_get_browser", lambda: None)()
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
    return _ORIGINAL_FULL_SYNC_PRUNE_GUARD(
        self,
        products,
        category_count,
        expected_category_occurrences,
        expected_products,
    )


def activate() -> None:
    """Install authoritative detail-page SKU recovery once."""
    global _PATCHED
    if _PATCHED:
        return
    CategoryProductSyncService._full_sync_prune_guard = _full_sync_prune_guard
    _PATCHED = True


activate()

__all__ = ["activate"]
