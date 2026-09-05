from __future__ import annotations

from services.scraping.category_product_sync_service import (
    CategoryProductSyncService,
)


class NormalizedCategoryProductSyncService(CategoryProductSyncService):
    """Extiende el sync existente con persistencia normalizada del scraping."""

    def __init__(self, *args, normalized_repository=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.normalized_repository = normalized_repository

    def sync_categories(self, categories, progress_callback=None):
        products = super().sync_categories(categories, progress_callback)
        self._persist_normalized(categories, products, mode="full")
        return products

    def sync_category(self, category_url, category=""):
        products = super().sync_category(category_url, category)
        category_object = type(
            "ScrapedCategory",
            (),
            {
                "name": category,
                "url": category_url,
                "expected_count": 0,
            },
        )()
        self._persist_normalized([category_object], products, mode="directed")
        return products

    def _persist_normalized(self, categories, products, *, mode: str) -> None:
        repository = self.normalized_repository
        if repository is None or self.catalog_sync_service is None:
            return

        result = self.last_sync_result
        run_id = repository.start_run(
            mode=mode,
            categories_requested=len(categories),
            expected_category_occurrences=getattr(
                result,
                "expected_category_occurrences",
                0,
            ),
        )
        try:
            actual = repository.persist_occurrences(
                run_id,
                categories,
                products,
                self.catalog_sync_service.repository,
            )
            repository.finish_run(
                run_id,
                result=result,
                actual_category_occurrences=actual,
            )
        except Exception as error:
            repository.finish_run(
                run_id,
                result=result,
                actual_category_occurrences=0,
                message=f"normalized persistence error: {error}",
            )
            raise
