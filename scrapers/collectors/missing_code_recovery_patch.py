"""Compatibility facade for the retired missing-SKU monkey patch."""

from __future__ import annotations

from typing import Any

from scrapers.extractors.product_extractor import ProductExtractor


def _recover_one(product: Any, browser: Any, extractor: ProductExtractor) -> bool:
    """Preserve the historical single-product recovery helper API."""
    from services.scraping.category_product_sync_service import (
        CategoryProductSyncService,
    )

    return bool(
        CategoryProductSyncService._recover_one_missing_code(
            product,
            browser,
            extractor,
        )
    )


def _recover_missing_codes(service, products) -> int:
    """Delegate SKU recovery to the canonical sync service."""
    recover = getattr(service, "_recover_missing_codes", None)
    if not callable(recover):
        return 0
    return int(recover(products) or 0)


def _full_sync_prune_guard(
    service,
    products,
    category_count,
    expected_category_occurrences=0,
    expected_products=None,
):
    """Preserve the historical helper API without runtime patching."""
    guard = getattr(service, "_full_sync_prune_guard", None)
    if not callable(guard):
        raise TypeError("service does not expose _full_sync_prune_guard")
    return guard(
        products,
        category_count,
        expected_category_occurrences=expected_category_occurrences,
        expected_products=expected_products,
    )


def activate() -> None:
    """Preserve the historical activation API without side effects."""
    return None


__all__ = ["activate"]
