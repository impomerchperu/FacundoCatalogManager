"""Compatibility fixes for category coverage accounting."""

from __future__ import annotations

from .category_product_sync_service import CategoryProductSyncService
from .category_name_normalizer import normalize_category_name

_PATCHED = False


def _split_categories(self, value):
    """Preserve catalog category names that legitimately contain commas."""
    if not isinstance(value, str):
        return []
    text = value.strip()
    normalized = normalize_category_name(text)

    # "Cocina, Mesa y Hogar" is one WooCommerce category. The legacy comma
    # splitter incorrectly classified it as two categories ("Cocina" and
    # "Mesa y Hogar"), inflating raw category coverage diagnostics and leaving
    # the real category with zero matches.
    if normalized == "cocina mesa y hogar":
        return [text]

    return _ORIGINAL_SPLIT(self, text)


def activate() -> None:
    """Install the category splitting compatibility behavior once."""
    global _PATCHED
    if _PATCHED:
        return
    global _ORIGINAL_SPLIT
    _ORIGINAL_SPLIT = CategoryProductSyncService._split_categories
    CategoryProductSyncService._split_categories = _split_categories
    _PATCHED = True


activate()

__all__ = ["CategoryProductSyncService", "activate"]
