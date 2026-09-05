"""Public exports for scraping services.

Imports that wire the complete scraping factory are kept lazy so low-level
repositories can import individual scraping helpers without circular imports.
"""

from .catalog_sync_service import CatalogSyncService
from .category_pagination_service import CategoryPaginationService
from .category_product_scraping_service import CategoryProductScrapingService
from .category_product_sync_service import CategoryProductSyncService
from .category_service import CategoryService
from .full_scraping_service import FullScrapingService
from .image_sync_adapter import ImageSyncAdapter
from .product_diff_service import ProductDiffService
from .product_hash_service import ProductHashService
from .scraped_product_mapper import ScrapedProductMapper
from .scraped_product_persistence_service import ScrapedProductPersistenceService
from .scraped_product_service import ScrapedProductService
from .scraping_config import ScrapingConfig
from .scraping_runner import ScrapingRunner
from .scraping_session import ScrapingSession, ScrapingSessionResult

__all__ = [
    "CatalogSyncService",
    "CategoryPaginationService",
    "CategoryProductScrapingService",
    "CategoryProductSyncService",
    "CategoryService",
    "FullScrapingService",
    "ImageSyncAdapter",
    "ProductDiffService",
    "ProductHashService",
    "ScrapedProductMapper",
    "ScrapedProductPersistenceService",
    "ScrapedProductService",
    "ScrapingConfig",
    "ScrapingFactory",
    "ScrapingRunner",
    "ScrapingSession",
    "ScrapingSessionResult",
]


def __getattr__(name: str):
    """Load the factory only when it is explicitly requested."""
    if name == "ScrapingFactory":
        from .scraping_factory import ScrapingFactory

        return ScrapingFactory
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
