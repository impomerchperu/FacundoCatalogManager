def test_public_scraping_service_exports_match_current_api():
    from services import scraping

    expected_exports = {
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
    }

    assert set(scraping.__all__) == expected_exports
    assert all(getattr(scraping, name) is not None for name in expected_exports)
