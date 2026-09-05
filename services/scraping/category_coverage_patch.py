"""Legacy compatibility hook for category coverage behavior."""

from __future__ import annotations


_PATCHED = False


def activate() -> None:
    """Keep the legacy hook import-safe after category normalization refactor."""
    global _PATCHED
    _PATCHED = True


activate()

__all__ = ["activate"]
