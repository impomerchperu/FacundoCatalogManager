from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from scrapers.images.image_repository import ImageRepository
from scrapers.images.safe_image_manager import SafeImageManager


class ImageSync:
    """Sincronización incremental de imágenes por código y URL."""

    def __init__(
        self,
        image_manager=None,
        image_repository=None,
        max_workers=8,
    ):
        self.image_manager = image_manager or SafeImageManager()
        self.image_repository = image_repository or ImageRepository()
        self.max_workers = int(max_workers)
        if self.max_workers <= 0:
            raise ValueError("max_workers debe ser mayor que cero.")

    def synchronize(self, product, old_product=None):
        result = self.sync_product(product, old_product)
        return {
            "image_path": getattr(result, "image_path", ""),
            "image_hash": getattr(result, "image_hash", ""),
        }

    def process(self, products):
        items = list(products or [])
        if not items:
            return []
        if len(items) == 1 or self.max_workers == 1:
            return [self.sync_product(product) for product in items]

        worker_count = min(self.max_workers, len(items))
        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            futures = [
                executor.submit(self.sync_product, product)
                for product in items
            ]
            return [future.result() for future in futures]

    def sync_product(self, product, old_product=None):
        image_url = getattr(product, "image_url", "")
        if not image_url:
            return product

        existing = self.image_repository.find(product.code, image_url)
        old_url = self._get(old_product, "image_url")
        url_changed = bool(old_product and old_url and old_url != image_url)

        if existing and not url_changed:
            product.image_path = existing["image_path"]
            product.image_hash = existing.get("image_hash", "")
            return product

        if url_changed:
            image_data = self.image_manager.process(
                product.code,
                image_url,
                force=True,
            )
        else:
            image_data = self.image_manager.process(
                product.code,
                image_url,
            )

        product.image_path = image_data.get("image_path", "")
        product.image_hash = image_data.get("image_hash", "")
        return product

    @staticmethod
    def _get(product, field):
        if isinstance(product, dict):
            return product.get(field, "")
        return getattr(product, field, "") if product is not None else ""
