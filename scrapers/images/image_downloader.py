from __future__ import annotations

import hashlib
from pathlib import Path

import requests


class ImageDownloader:
    """Descarga una imagen usando un nombre canónico basado en el código."""

    def __init__(self, output_dir: str | Path = "data/images/products"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def download(self, code: str, url: str) -> str:
        response = requests.get(
            url,
            timeout=30,
            headers={"User-Agent": "FacundoCatalogManager/1.0"},
        )
        response.raise_for_status()

        extension = self._extension(url, response.headers.get("Content-Type", ""))
        target = self.output_dir / f"{self._safe_code(code)}{extension}"
        temporary = target.with_suffix(target.suffix + ".tmp")
        temporary.write_bytes(response.content)
        temporary.replace(target)
        return target.as_posix()

    @staticmethod
    def _safe_code(code: str) -> str:
        value = str(code).strip()
        return "".join(char if char.isalnum() or char in "-_" else "_" for char in value)

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
