"""Public exports for scraping services.

Imports that wire the complete scraping factory are kept lazy so low-level
repositories can import individual scraping helpers without circular imports.
"""

from typing import TYPE_CHECKING

from . import category_coverage_patch as _category_coverage_patch
from . import prune_guard_recovery_patch as _prune_guard_recovery_patch
from .catalog_sync_service import CatalogSyncService
from .category_product_scraping_service import CategoryProductScrapingService
from .category_product_sync_service import CategoryProductSyncService
from .category_service import CategoryService
from .image_sync_adapter import ImageSyncAdapter
from .product_diff_service import ProductDiffService
from .product_hash_service import ProductHashService
from .scraped_product_mapper import ScrapedProductMapper
from .scraped_product_persistence_service import ScrapedProductPersistenceService
from .scraping_config import ScrapingConfig
from .scraping_runner import ScrapingRunner
from .scraping_session import ScrapingSession, ScrapingSessionResult

if TYPE_CHECKING:
    from .scraping_factory import ScrapingFactory

_category_coverage_patch.activate()
_prune_guard_recovery_patch.activate()

__all__ = [
    "CatalogSyncService",
    "CategoryProductScrapingService",
    "CategoryProductSyncService",
    "CategoryService",
    "ImageSyncAdapter",
    "ProductDiffService",
    "ProductHashService",
    "ScrapedProductMapper",
    "ScrapedProductPersistenceService",
    "ScrapingConfig",
    "ScrapingFactory",
    "ScrapingRunner",
    "ScrapingSession",
    "ScrapingSessionResult",
]


def __getattr__(name: str):
    """Load the factory export only when requested."""
    if name != "ScrapingFactory":
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

    module = __import__(
        f"{__name__}.scraping_factory",
        fromlist=[name],
    )
    value = getattr(module, name)
    globals()[name] = value
    return value
