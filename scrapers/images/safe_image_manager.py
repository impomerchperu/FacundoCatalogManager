from __future__ import annotations

from pathlib import Path

from scrapers.images.image_downloader import ImageDownloader
from scrapers.images.image_repository import ImageRepository


class SafeImageManager:
    """Descarga imágenes y maneja fallos sin propagar rutas inválidas."""

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

        try:
            path = self.downloader.download(code, url)
            if not path:
                return self._error_result()

            image_path = Path(path)
            if not image_path.is_file():
                return self._error_result()

            return {
                "image_path": path,
                "image_hash": ImageDownloader.hash_file(image_path),
            }
        except (OSError, ValueError, RuntimeError) as error:
            return self._error_result(str(error) or "Download failed")

    @staticmethod
    def _error_result(message: str = "Download failed") -> dict:
        return {
            "image_path": "",
            "image_hash": "",
            "image_error": message,
        }
