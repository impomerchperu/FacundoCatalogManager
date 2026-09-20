from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import ClassVar

from scrapers.images.image_hash import ImageHash
from scrapers.images.image_paths import IMAGE_PRODUCTS_DIR


class ImageAuditService:
    """Audita duplicados físicos sin borrar archivos durante una auditoría."""

    IMAGE_EXTENSIONS: ClassVar[set[str]] = {
        ".jpg",
        ".jpeg",
        ".png",
        ".webp",
        ".gif",
    }

    def __init__(self, image_root: str | Path = IMAGE_PRODUCTS_DIR):
        self.image_root = Path(image_root)

    def audit(self) -> dict:
        groups: dict[str, list[str]] = defaultdict(list)
        if self.image_root.exists():
            for path in self.image_root.rglob("*"):
                if (
                    path.is_file()
                    and path.suffix.lower() in self.IMAGE_EXTENSIONS
                ):
                    groups[self._hash(path)].append(path.as_posix())

        duplicates = [paths for paths in groups.values() if len(paths) > 1]
        return {
            "root": self.image_root.as_posix(),
            "files": sum(len(paths) for paths in groups.values()),
            "unique_hashes": len(groups),
            "duplicate_groups": len(duplicates),
            "duplicate_files": sum(len(paths) - 1 for paths in duplicates),
            "duplicates": duplicates,
        }

    def remove_duplicates(self) -> dict:
        """Mantiene compatibilidad sin permitir borrado físico desde el auditor."""
        raise RuntimeError(
            "La limpieza destructiva de imágenes está deshabilitada; "
            "use la sincronización normalizada del catálogo."
        )

    @staticmethod
    def _hash(path: Path) -> str:
        return ImageHash().calculate(path)
