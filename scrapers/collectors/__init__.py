"""Collectors package initialization."""

# Only runtime compatibility layers that still add behavior are activated here.
from . import jsf_concurrency_patch as _jsf_concurrency_patch
from . import page_metrics_patch as _page_metrics_patch
from . import price_detail_recovery_patch as _price_detail_recovery_patch

__all__ = [
    "_jsf_concurrency_patch",
    "_page_metrics_patch",
    "_price_detail_recovery_patch",
]
