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


def _sync_products_with_safety(
    self,
    products,
    full_sync=False,
    allow_prune=False,
    expected_products=0,
    expected_category_occurrences=0,
):
    del allow_prune
    coverage_validated = getattr(self, "_full_sync_coverage_validated", None)
    if full_sync and coverage_validated is False:
        reason = str(
            getattr(self, "_full_sync_coverage_reason", "unknown") or "unknown"
        )
        self.last_sync_result.errors.append(
            "Cobertura del catálogo incompleta: "
            f"sincronización FULL omitida por seguridad ({reason})."
        )
        return list(products or [])

    return _ORIGINAL_SYNC_PRODUCTS(
        self,
        products,
        full_sync=full_sync,
        allow_prune=True,
        expected_products=expected_products,
        expected_category_occurrences=expected_category_occurrences,
    )


def activate() -> None:
    """Install the FULL-sync safety layer exactly once."""
    global _PATCHED
    if _PATCHED:
        return
    CategoryProductSyncService.sync_categories = _sync_categories_with_safety
    CategoryProductSyncService._full_sync_prune_guard = _coverage_guard_with_state
    CategoryProductSyncService.sync_products = _sync_products_with_safety
    _PATCHED = True


activate()

__all__ = ["activate"]
