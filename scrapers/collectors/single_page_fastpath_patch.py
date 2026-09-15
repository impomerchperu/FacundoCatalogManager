"""Legacy compatibility facade for the retired archive first-page fast path."""

from __future__ import annotations

_PATCHED = True


def activate() -> None:
    """Preserve the historical activation API without monkey-patching."""
    return None


__all__ = ["activate"]
