def test_public_scraping_service_exports_remain_available():
    import services.scraping as scraping

    expected_exports = {
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
    }

    assert set(scraping.__all__) == expected_exports
    assert all(getattr(scraping, name) is not None for name in expected_exports)
