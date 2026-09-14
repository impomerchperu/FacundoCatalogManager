"""Collectors package initialization."""

# Only runtime compatibility layers that still add behavior are activated here.
from . import page_metrics_patch as _page_metrics_patch
from . import price_detail_recovery_patch as _price_detail_recovery_patch

__all__ = [
    "_page_metrics_patch",
    "_price_detail_recovery_patch",
]
