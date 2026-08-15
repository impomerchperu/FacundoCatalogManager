from __future__ import annotations

from pathlib import Path

from scrapers.images.image_downloader import ImageDownloader
from scrapers.images.image_repository import ImageRepository


class ImageManager:
    """Descarga imágenes y devuelve siempre la ruta y hash resultantes."""

    def __init__(
        self,
        downloader: ImageDownloader | None = None,
        repository: ImageRepository | None = None,
    ):
        self.downloader = downloader or ImageDownloader()
        self.repository = repository or ImageRepository()

    def process(self, code: str, url: str, force: bool = False) -> dict:
        if not force:
            existing = self.repository.find(code)
            if existing:
                return existing

        path = self.downloader.download(code, url)
        return {
            "image_path": path,
            "image_hash": ImageDownloader.hash_file(Path(path)),
        }
