from __future__ import annotations

from pathlib import Path

from config.runtime_paths import to_data_relative_path
from scrapers.images.image_paths import (
    IMAGE_EXTENSIONS,
    IMAGE_PRODUCTS_DIR,
    product_image_directory,
    safe_image_code,
)


class ImageNamer:
    """Genera nombres de archivo canónicos a partir del código de producto."""

    def __init__(self, base_dir: str | Path = IMAGE_PRODUCTS_DIR):
        self.base_dir = Path(base_dir)

    def build(self, code: str, image_url: str) -> str:
        extension = self._extract_extension(image_url)
        safe_code = safe_image_code(code)
        directory = product_image_directory(safe_code, root=self.base_dir)
        return to_data_relative_path(directory / f"{safe_code}-01{extension}")

    @staticmethod
    def _extract_extension(image_url: str) -> str:
        suffix = Path(image_url.split("?", 1)[0]).suffix.lower()
        return suffix if suffix in IMAGE_EXTENSIONS else ".bin"
