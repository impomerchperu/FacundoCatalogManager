from __future__ import annotations

import hashlib
from pathlib import Path


class ImageHash:
    """Genera hashes SHA-256 para archivos de imagen."""

    ALGORITHM = "sha256"

    def calculate(self, image_path: str) -> str:
        if not image_path:
            return ""

        path = Path(image_path)
        if not path.exists():
            return ""

        sha = hashlib.sha256()
        with path.open("rb") as file:
            while chunk := file.read(8192):
                sha.update(chunk)

        return sha.hexdigest()
