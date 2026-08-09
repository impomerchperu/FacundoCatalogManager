import hashlib
import json
from typing import ClassVar


class ProductHashService:
    """Genera hashes para detectar cambios en productos e imágenes."""

    CONTENT_FIELDS: ClassVar[list[str]] = [
        "code",
        "name",
        "category",
        "description",
        "price",
        "price_sample",
        "price_hundred",
        "price_thousand",
        "stock",
        "colors",
        "color_stock",
    ]

    IMAGE_FIELDS: ClassVar[list[str]] = [
        "image_url",
        "image_path",
    ]

    def generate(self, product) -> str:
        return self.generate_content_hash(product)

    def generate_content_hash(self, product) -> str:
        return self._generate_hash(product, self.CONTENT_FIELDS)

    def generate_image_hash(self, product) -> str:
        return self._generate_hash(product, self.IMAGE_FIELDS)

    def _generate_hash(self, product, fields) -> str:
        data = {
            field: self._normalize(self._get_value(product, field))
            for field in fields
        }
        payload = json.dumps(
            data,
            sort_keys=True,
            ensure_ascii=False,
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    @staticmethod
    def _get_value(product, field):
        if isinstance(product, dict):
            return product.get(field)
        return getattr(product, field, None)

    @staticmethod
    def _normalize(value):
        if isinstance(value, str):
            return value.strip()
        return value
