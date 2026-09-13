from __future__ import annotations

import hashlib
import time
from pathlib import Path

import requests


class ImageDownloader:
    """Descarga una imagen usando un nombre canónico basado en el código."""

    def __init__(
        self,
        output_dir: str | Path = "data/images/products",
        request_timeout: int = 30,
        max_retries: int = 2,
    ):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.request_timeout = int(request_timeout)
        self.max_retries = int(max_retries)
        if self.request_timeout <= 0:
            raise ValueError("request_timeout debe ser mayor que cero.")
        if self.max_retries <= 0:
            raise ValueError("max_retries debe ser mayor que cero.")

    def download(self, code: str, url: str) -> str:
        last_error = None
        for attempt in range(self.max_retries):
            try:
                response = requests.get(
                    url,
                    timeout=self.request_timeout,
                    headers={"User-Agent": "FacundoCatalogManager/1.0"},
                )
                response.raise_for_status()

                extension = self._extension(
                    url,
                    response.headers.get("Content-Type", ""),
                )
                target = self.output_dir / (
                    f"{self._safe_code(code)}{extension}"
                )
                temporary = target.with_suffix(target.suffix + ".tmp")
                temporary.write_bytes(response.content)
                temporary.replace(target)
                return target.as_posix()
            except requests.exceptions.RequestException as error:
                last_error = error
                if not self._is_retryable_error(error):
                    raise
                if attempt < self.max_retries - 1:
                    time.sleep(attempt + 1)

        if last_error:
            raise last_error
        raise RuntimeError("No se pudo descargar la imagen.")

    @staticmethod
    def _is_retryable_error(error):
        if isinstance(
            error,
            (
                requests.exceptions.ConnectionError,
                requests.exceptions.Timeout,
            ),
        ):
            return True

        if isinstance(error, requests.exceptions.HTTPError):
            response = getattr(error, "response", None)
            status_code = getattr(response, "status_code", None)
            return status_code == 429 or (
                isinstance(status_code, int) and status_code >= 500
            )

        return False

    @staticmethod
    def _safe_code(code: str) -> str:
        value = str(code).strip()
        return "".join(
            char if char.isalnum() or char in "-_" else "_"
            for char in value
        )

    @staticmethod
    def _extension(url: str, content_type: str) -> str:
        suffix = Path(url.split("?", 1)[0]).suffix.lower()
        if suffix in {".jpg", ".jpeg", ".png", ".webp", ".gif"}:
            return suffix

        mapping = {
            "image/jpeg": ".jpg",
            "image/png": ".png",
            "image/webp": ".webp",
            "image/gif": ".gif",
        }
        return mapping.get(content_type.split(";", 1)[0].lower(), ".jpg")

    @staticmethod
    def hash_file(path: str | Path) -> str:
        digest = hashlib.sha256()
        with Path(path).open("rb") as file:
            for chunk in iter(lambda: file.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()
