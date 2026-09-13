"""Prevent partial FULL scrapes from mutating the catalog."""

from __future__ import annotations

from services.scraping.category_product_sync_service import CategoryProductSyncService

_PATCHED = False
_ORIGINAL_SYNC_CATEGORIES = CategoryProductSyncService.sync_categories
_ORIGINAL_COVERAGE_GUARD = CategoryProductSyncService._full_sync_prune_guard
_ORIGINAL_SYNC_PRODUCTS = CategoryProductSyncService.sync_products


def _sync_categories_with_safety(self, categories, progress_callback=None):
    self._full_sync_coverage_validated = None
    self._full_sync_coverage_reason = ""
    return _ORIGINAL_SYNC_CATEGORIES(self, categories, progress_callback)


def _coverage_guard_with_state(
    self,
    products,
    category_count,
    *,
    expected_category_occurrences=0,
    expected_products=None,
):
    complete, reason = _ORIGINAL_COVERAGE_GUARD(
        self,
        products,
        category_count,
        expected_category_occurrences=expected_category_occurrences,
        expected_products=expected_products,
    )
    self._full_sync_coverage_validated = bool(complete)
    self._full_sync_coverage_reason = str(reason or "unknown")
    return complete, reason


def _demonstrates_complete_coverage(
    self,
    products,
    *,
    expected_products=0,
    expected_category_occurrences=0,
) -> bool:
    """Verify final collected coverage independently of transient HTTP errors."""
    raw_products = list(products or [])
    if not raw_products:
        return False

    if any(not str(getattr(product, "code", "") or "").strip() for product in raw_products):
        return False

    expected_occurrences = max(int(expected_category_occurrences or 0), 0)
    if expected_occurrences <= 0 or len(raw_products) < expected_occurrences:
        return False

    summary = getattr(self.last_sync_result, "category_summary", []) or []
    if summary:
        for row in summary:
            expected = max(int(row.get("expected", 0) or 0), 0)
            if expected <= 0:
                continue
            products_found = int(row.get("products", 0) or 0)
            unique_found = int(row.get("unique_products", 0) or 0)
            if products_found != expected or unique_found != expected:
                return False
    else:
        actual_occurrences = int(
            getattr(self.last_sync_result, "products_found", len(raw_products)) or 0
        )
        if actual_occurrences < expected_occurrences:
            return False

    if expected_products:
        unique_codes = {
            str(getattr(product, "code", "")).strip().casefold()
            for product in raw_products
            if str(getattr(product, "code", "")).strip()
        }
        if len(unique_codes) < max(int(expected_products), 0):
            return False

    return True


def _sync_products_with_safety(
    self,
    products,
    full_sync=False,
    allow_prune=False,
    expected_products=0,
    expected_category_occurrences=0,
):
    coverage_validated = getattr(self, "_full_sync_coverage_validated", None)
    if full_sync and coverage_validated is False:
        recovered = _demonstrates_complete_coverage(
            self,
            products,
            expected_products=expected_products,
            expected_category_occurrences=expected_category_occurrences,
        )
        if not recovered:
            reason = str(
                getattr(self, "_full_sync_coverage_reason", "unknown") or "unknown"
            )
            self.last_sync_result.errors.append(
                "Cobertura del catálogo incompleta: "
                f"sincronización FULL omitida por seguridad ({reason})."
            )
            return list(products or [])
        allow_prune = True
        self._full_sync_coverage_validated = True
        self._full_sync_coverage_reason = "complete"

    return _ORIGINAL_SYNC_PRODUCTS(
        self,
        products,
        full_sync=full_sync,
        allow_prune=allow_prune,
        expected_products=expected_products,
        expected_category_occurrences=expected_category_occurrences,
    )


def activate() -> None:
    """Install the FULL-sync safety layer exactly once."""
    global _PATCHED
    if _PATCHED:
        return
    if CategoryProductSyncService.sync_categories is _sync_categories_with_safety:
        _PATCHED = True
        return
    CategoryProductSyncService.sync_categories = _sync_categories_with_safety
    CategoryProductSyncService._full_sync_prune_guard = _coverage_guard_with_state
    CategoryProductSyncService.sync_products = _sync_products_with_safety
    _PATCHED = True


activate()

__all__ = ["activate"]
