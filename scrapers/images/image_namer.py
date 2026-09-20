from __future__ import annotations

from pathlib import Path

from scrapers.images.image_paths import IMAGE_PRODUCTS_DIR


class ImageNamer:
    """Genera nombres de archivo canónicos a partir del código de producto."""

    def __init__(self, base_dir: str | Path = IMAGE_PRODUCTS_DIR):
        self.base_dir = Path(base_dir)

    def build(self, code: str, image_url: str) -> str:
        extension = self._extract_extension(image_url)
        return (self.base_dir / f"{code}{extension}").as_posix()

    @staticmethod
    def _extract_extension(image_url: str) -> str:
        suffix = Path(image_url.split("?", 1)[0]).suffix.lower()
        return suffix or ".bin"
