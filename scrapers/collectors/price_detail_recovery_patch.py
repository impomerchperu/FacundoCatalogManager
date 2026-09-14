"""Compatibility facade for the explicit price-recovery collector."""

from __future__ import annotations

from .price_recovery_product_collection_scraper import (
    PriceRecoveryProductCollectionScraper,
)

_PATCHED = False


def activate() -> None:
    """Preserve the historical activation API without monkey-patching runtime code."""
    return None


__all__ = ["PriceRecoveryProductCollectionScraper", "activate"]
