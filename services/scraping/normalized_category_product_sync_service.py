from __future__ import annotations

from services.scraping.category_name_normalizer import (
    canonical_category_name,
    normalize_category_name,
    split_category_names,
)
from services.scraping.category_product_sync_service import CategoryProductSyncService


class NormalizedCategoryProductSyncService(CategoryProductSyncService):
    """Extiende el sync existente con persistencia normalizada del scraping."""

    def __init__(self, *args, normalized_repository=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.normalized_repository = normalized_repository

    def sync_categories(self, categories, progress_callback=None):
        products = super().sync_categories(categories, progress_callback)
        mode = getattr(self, "_scraping_mode", "directed")
        self._align_multiple_category_result(categories, products)
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

    def _full_sync_prune_guard(
        self,
        products,
        category_count,
        *,
        expected_category_occurrences=0,
        expected_products=None,
    ):
        return super()._full_sync_prune_guard(
            products,
            category_count,
            expected_category_occurrences=expected_category_occurrences,
            expected_products=expected_products,
        )

    def _align_multiple_category_result(self, categories, products):
        requested = {
            normalize_category_name(canonical_category_name(getattr(category, "name", "")))
            for category in categories
        }
        requested.discard("")
        by_code = {}
        product_by_code = {}
        for product in products or []:
            code = str(getattr(product, "code", "")).strip()
            code_key = code.casefold()
            if not code_key:
                continue
            product_by_code[code_key] = product
            category_map = by_code.setdefault(code_key, {})
            for value in split_category_names(getattr(product, "category", "")):
                category_name = canonical_category_name(value)
                category_key = normalize_category_name(category_name)
                if category_key in requested:
                    category_map.setdefault(category_key, category_name)
        multiple = []
        for code_key, category_map in by_code.items():
            if len(category_map) <= 1:
                continue
            product = product_by_code[code_key]
            multiple.append(
                {
                    "code": str(getattr(product, "code", "")).strip(),
                    "name": str(getattr(product, "name", "")).strip(),
                    "categories": list(category_map.values()),
                }
            )
        self.last_sync_result.multiple_category_products = multiple
        self.last_sync_result.products_multiple_categories = len(multiple)

    def _full_coverage_ready(self, products) -> bool:
        """Autoriza maestros y ocurrencias solo con cobertura FULL explícitamente completa."""
        result = self.last_sync_result
        if (
            getattr(self, "_scraping_mode", "directed") != "full"
            or getattr(result, "missing_code", 0)
            or getattr(result, "errors", None)
            or getattr(result, "failures", None)
        ):
            return False

        expected_occurrences = max(
            int(getattr(result, "expected_category_occurrences", 0) or 0),
            0,
        )
        actual_occurrences = len(products or [])
        if expected_occurrences <= 0 or actual_occurrences < expected_occurrences:
            return False

        summary = getattr(result, "category_summary", []) or []
        if not summary:
            return False
        for row in summary:
            expected = max(int(row.get("expected", 0) or 0), 0)
            if expected <= 0:
                continue
            products_found = int(row.get("products", 0) or 0)
            unique_found = int(row.get("unique_products", 0) or 0)
            if products_found != expected or unique_found != expected:
                return False

        return True

    def _ensure_full_catalog_masters(self, products) -> None:
        """Garantiza la FK maestra antes de persistir ocurrencias de un FULL válido."""
        if not self._full_coverage_ready(products):
            return

        catalog_sync_service = self.catalog_sync_service
        if catalog_sync_service is None:
            return
        product_repository = catalog_sync_service.repository
        seen = set()
        for product in products or []:
            code = str(getattr(product, "code", "")).strip().upper()
            if not code or code.casefold() in seen:
                continue
            seen.add(code.casefold())
            if product_repository.get(code) is None:
                product_repository.save(product)

    def _persist_normalized(self, categories, products, *, mode: str) -> None:
        repository = self.normalized_repository
        catalog_sync_service = self.catalog_sync_service
        if repository is None or catalog_sync_service is None:
            return

        if mode == "full" and not self._full_coverage_ready(products):
            return

        self._ensure_full_catalog_masters(products)
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
                catalog_sync_service.repository,
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

        products_by_category: dict[str, list[str]] = {}
        for product in products:
            code = str(getattr(product, "code", "")).strip().casefold()
            if not code:
                continue
            for category_name in split_category_names(
                getattr(product, "category", "")
            ):
                category_key = normalize_category_name(category_name)
                if category_key:
                    products_by_category.setdefault(category_key, []).append(code)

        metadata = {}
        for category in categories:
            category_name = canonical_category_name(getattr(category, "name", ""))
            category_key = normalize_category_name(category_name)
            category_url = self._canonical_url(getattr(category, "url", ""))
            metrics = self._find_category_metrics(page_metrics, category_url)
            if not metrics or not category_key:
                continue

            codes = products_by_category.get(category_key, [])
            code_index = 0
            for page in metrics.get("pages", []):
                page_number = max(int(page.get("page", 0) or 0), 0)
                unique_count = max(int(page.get("unique_products", 0) or 0), 0)
                for position in range(1, unique_count + 1):
                    if code_index >= len(codes):
                        break
                    metadata[(category_key, codes[code_index])] = (
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
