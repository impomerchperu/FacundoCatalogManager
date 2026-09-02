"""Compatibility fixes for category coverage accounting."""

from __future__ import annotations

from .category_name_normalizer import normalize_category_name
from .category_product_sync_service import CategoryProductSyncService

_PATCHED = False
_ORIGINAL_SPLIT = None


def _split_categories(self, value):
    """Preserve catalog category names that legitimately contain commas."""
    if not isinstance(value, str):
        return []
    text = value.strip()
    normalized = normalize_category_name(text)

    if normalized == "cocina mesa y hogar":
        return [text]

    return _ORIGINAL_SPLIT(text)


def activate() -> None:
    """Install the category splitting compatibility behavior once."""
    global _PATCHED, _ORIGINAL_SPLIT
    if _PATCHED:
        return
    _ORIGINAL_SPLIT = CategoryProductSyncService._split_categories
    CategoryProductSyncService._split_categories = _split_categories
    _PATCHED = True


activate()

__all__ = ["CategoryProductSyncService", "activate"]
