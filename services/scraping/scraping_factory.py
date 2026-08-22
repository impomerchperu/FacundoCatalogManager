
        sync_service = CategoryProductSyncService(
            product_scraping_service,
            scraped_persistence,
            mapper,
            catalog_sync_service,
            image_sync_adapter,
        )

        return ScrapingRunner(
            sync_service,
            config=config,
            category_service=category_service,
            history_repository=history_repository,
            catalog_repository=product_repository,
        )
