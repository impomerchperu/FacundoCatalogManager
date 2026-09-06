from __future__ import annotations

from pathlib import Path
from typing import ClassVar

from PIL import Image


class ImageValidator:
    """Valida extensión, contenido y estructura de archivos de imagen."""

    VALID_EXTENSIONS: ClassVar[set[str]] = {
        ".jpg",
        ".jpeg",
        ".png",
        ".webp",
    }

    def is_valid_extension(self, filename: str) -> bool:
        extension = Path(filename).suffix.lower()
        return extension in self.VALID_EXTENSIONS

    def is_valid_content(self, content: bytes) -> bool:
        if not content:
            return False

        signatures = (
            b"\xff\xd8",
            b"\x89PNG",
            b"RIFF",
        )
        return any(content.startswith(signature) for signature in signatures)

    def is_valid_file(self, path: str) -> bool:
        image_path = Path(path)
        if not image_path.exists():
            return False
        if image_path.stat().st_size == 0:
            return False
        return self.is_valid_extension(image_path.name)

    def validate(self, path: str) -> bool:
        image_path = Path(path)
        if not self.is_valid_file(path):
            return False

        try:
            with Image.open(image_path) as image:
                image.verify()
        except (OSError, ValueError):
            return False

        return True

    def is_valid(self, path: str) -> bool:
        return self.validate(path)
