def test_public_scraping_service_exports_remain_available():
    from services.scraping import (
        CategoryPaginationService,
        CategoryProductScrapingService,
        CategoryProductSyncService,
        CategoryService,
        FullScrapingService,
        ScrapedProductMapper,
        ScrapedProductPersistenceService,
        ScrapedProductService,
        ScrapingConfig,
        ScrapingFactory,
        ScrapingRunner,
        ScrapingSession,
    )

    exported = (
        CategoryPaginationService,
        CategoryProductScrapingService,
        CategoryProductSyncService,
        CategoryService,
        FullScrapingService,
        ScrapedProductMapper,
        ScrapedProductPersistenceService,
        ScrapedProductService,
        ScrapingConfig,
        ScrapingFactory,
        ScrapingRunner,
        ScrapingSession,
    )

    assert all(exported)
