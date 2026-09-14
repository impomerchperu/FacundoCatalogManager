"""Compatibility facade for the consolidated price-recovery policy."""

from __future__ import annotations

from .product_collection_scraper import ProductCollectionScraper

PriceRecoveryProductCollectionScraper = ProductCollectionScraper


def activate() -> None:
    """Preserve the historical activation API without monkey-patching runtime code."""
    return None


__all__ = ["PriceRecoveryProductCollectionScraper", "activate"]
