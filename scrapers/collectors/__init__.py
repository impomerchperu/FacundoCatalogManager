"""Collectors package initialization."""

# Only runtime compatibility layers that still add behavior are activated here.
from . import price_detail_recovery_patch as _price_detail_recovery_patch

__all__ = [
    "_price_detail_recovery_patch",
]
