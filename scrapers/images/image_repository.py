from __future__ import annotations

from pathlib import Path

from scrapers.images.image_downloader import ImageDownloader


class ImageRepository:
    """Localiza imágenes por código y calcula su hash cuando es necesario."""

    def __init__(self, output_dir: str | Path = "data/images/products"):
        self.output_dir = Path(output_dir)

    def find(self, code: str) -> dict | None:
        safe_code = ImageDownloader._safe_code(code)
        if not self.output_dir.exists():
            return None

        matches = sorted(
            path
            for path in self.output_dir.glob(f"{safe_code}.*")
            if path.is_file() and path.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp", ".gif"}
        )
        if not matches:
            return None

        path = matches[0]
        return {
            "image_path": path.as_posix(),
            "image_hash": ImageDownloader.hash_file(path),
        }
