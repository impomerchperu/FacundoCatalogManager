"""Ensure missing product prices always trigger detail-page enrichment."""

from __future__ import annotations

from .product_collection_scraper import ProductCollectionScraper

_PATCHED = False
_ORIGINAL_DETAIL_SKIP_REASON = ProductCollectionScraper._detail_skip_reason


def _missing_price_fields(card, product):
    """Treat every non-positive price field as missing."""
    del card
    return tuple(
        field
        for field in ProductCollectionScraper._PRICE_FIELDS
        if float(getattr(product, field, 0.0) or 0.0) <= 0
    )


def _detail_skip_reason(cls, card, product):
    """Never skip detail enrichment while any required price is missing."""
    if _missing_price_fields(card, product):
        return None
    return _ORIGINAL_DETAIL_SKIP_REASON.__func__(cls, card, product)


def activate() -> None:
    """Install the price recovery policy once."""
    global _PATCHED
    if _PATCHED:
        return
    ProductCollectionScraper._missing_price_fields = staticmethod(_missing_price_fields)
    ProductCollectionScraper._detail_skip_reason = classmethod(_detail_skip_reason)
    _PATCHED = True


activate()

__all__ = ["activate"]
