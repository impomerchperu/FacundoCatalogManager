from typing import Any, cast

import requests

from config.runtime_paths import resolve_data_path
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
            download_result = getattr(self.downloader, "download_result", None)
            if callable(download_result):
                raw_result = download_result(code, url)
                if not isinstance(raw_result, dict):
                    return self._error_result()
                result = cast(dict[str, Any], raw_result)
                path = str(result.get("image_path", "") or "")
                if not path:
                    return self._error_result()
                image_path = resolve_data_path(path)
                if not image_path.is_file():
                    return self._error_result()
                try:
                    verified = ImageDownloader.verify_image_file(image_path)
                except (OSError, ValueError) as error:
                    return self._error_result(
                        str(error) or "La imagen descargada no es identificable."
                    )
                actual_hash = verified["image_hash"]
                expected_hash = str(result.get("image_hash", "") or "")
                if not expected_hash or actual_hash != expected_hash:
                    return self._error_result("El hash descargado no coincide con el archivo.")
                return {**result, **verified}

            path = self.downloader.download(code, url)
            if not path:
                return self._error_result()

            image_path = resolve_data_path(path)
            if not image_path.is_file():
                return self._error_result()

            try:
                verified = ImageDownloader.verify_image_file(image_path)
            except (OSError, ValueError) as error:
                return self._error_result(
                    str(error) or "La imagen descargada no es identificable."
                )
            return {
                "image_path": path,
                "image_hash": verified["image_hash"],
            }
        except (
            OSError,
            ValueError,
            RuntimeError,
            requests.exceptions.RequestException,
        ) as error:
            return self._error_result(str(error) or "Download failed")

    @staticmethod
    def _error_result(message: str = "Download failed") -> dict:
        return {
            "image_path": "",
            "image_hash": "",
            "image_error": message,
        }
