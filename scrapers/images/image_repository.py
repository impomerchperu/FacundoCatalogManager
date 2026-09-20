from __future__ import annotations

from pathlib import Path

from scrapers.images.image_downloader import ImageDownloader
from scrapers.images.image_paths import IMAGE_EXTENSIONS, IMAGE_PRODUCTS_DIR


class ImageRepository:
    """Localiza imágenes por código y calcula su hash cuando es necesario."""

    def __init__(self, output_dir: str | Path = IMAGE_PRODUCTS_DIR):
        self.output_dir = Path(output_dir)

    def find(
        self,
        code: str,
        image_url: str | None = None,
    ) -> dict | None:
        safe_code = ImageDownloader._safe_code(code)
        if not self.output_dir.exists():
            return None

        if image_url:
            suffix = Path(image_url.split("?", 1)[0]).suffix.lower()
            if suffix in IMAGE_EXTENSIONS:
                preferred = self.output_dir / f"{safe_code}{suffix}"
                if preferred.is_file():
                    return {
                        "image_path": preferred.as_posix(),
                        "image_hash": ImageDownloader.hash_file(preferred),
                    }

        matches = sorted(
            path
            for path in self.output_dir.glob(f"{safe_code}.*")
            if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
        )
        if not matches:
            return None

        path = matches[0]
        return {
            "image_path": path.as_posix(),
            "image_hash": ImageDownloader.hash_file(path),
        }
