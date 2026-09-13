"""Compatibility facade for canonical category page coverage recovery."""

from __future__ import annotations

from .category_page_recovery import recover_missing_category_pages

_PATCHED = False


def activate() -> None:
    """Keep the historical import hook without installing monkey patches."""
    global _PATCHED
    _PATCHED = True


activate()

__all__ = ["activate", "recover_missing_category_pages"]
