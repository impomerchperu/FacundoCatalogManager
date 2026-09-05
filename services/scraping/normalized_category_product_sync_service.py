from __future__ import annotations

from services.scraping.category_product_sync_service import CategoryProductSyncService


class NormalizedCategoryProductSyncService(CategoryProductSyncService):
    """Extiende el sync existente con persistencia normalizada del scraping."""

    def __init__(self, *args, normalized_repository=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.normalized_repository = normalized_repository

    def sync_categories(self, categories, progress_callback=None):
        products = super().sync_categories(categories, progress_callback)
        mode = getattr(self, "_scraping_mode", "directed")
        self._persist_normalized(categories, products, mode=mode)
        return products

    def sync_category(self, category_url, category=""):
        products = super().sync_category(category_url, category)
        category_object = type(
            "ScrapedCategory",
            (),
            {"name": category, "url": category_url, "expected_count": 0},
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
                result, "expected_category_occurrences", 0
            ),
        )
        try:
            actual = repository.persist_occurrences(
                run_id,
                categories,
                products,
                self.catalog_sync_service.repository,
                occurrence_metadata=self._build_occurrence_metadata(
                    categories, products
                ),
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

    def _build_occurrence_metadata(self, categories, products):
        """Asocia cada producto extraído con su página y posición original."""
        scraper = getattr(self.scraper_service, "scraper", None)
        get_metrics = getattr(scraper, "get_page_metrics", None)
        if not callable(get_metrics):
            return {}

        page_metrics = get_metrics()
        if not page_metrics:
            return {}

        products_by_category = {}
        for product in products:
            category_name = str(getattr(product, "category", "")).strip().casefold()
            code = str(getattr(product, "code", "")).strip().casefold()
            if category_name and code:
                products_by_category.setdefault(category_name, []).append(code)

        metadata = {}
        for category in categories:
            category_name = str(getattr(category, "name", "")).strip().casefold()
            category_url = self._canonical_url(getattr(category, "url", ""))
            metrics = self._find_category_metrics(page_metrics, category_url)
            if not metrics:
                continue

            codes = products_by_category.get(category_name, [])
            code_index = 0
            for page in metrics.get("pages", []):
                page_number = max(int(page.get("page", 0) or 0), 0)
                unique_count = max(int(page.get("unique_products", 0) or 0), 0)
                for position in range(1, unique_count + 1):
                    if code_index >= len(codes):
                        break
                    metadata[(category_name, codes[code_index])] = (
                        page_number,
                        position,
                    )
                    code_index += 1
                if code_index >= len(codes):
                    break

        return metadata

    @staticmethod
    def _canonical_url(url: str) -> str:
        value = str(url or "").strip()
        if not value:
            return ""
        return value.split("#", 1)[0].split("?", 1)[0].rstrip("/").casefold()

    @classmethod
    def _find_category_metrics(cls, page_metrics, canonical_url):
        for url, metrics in page_metrics.items():
            if cls._canonical_url(url) == canonical_url:
                return metrics
        return None
