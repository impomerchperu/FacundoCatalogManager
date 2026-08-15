from __future__ import annotations

import hashlib
from collections import defaultdict
from pathlib import Path


class ImageAuditService:
    """Audita duplicados físicos sin borrar archivos durante una auditoría."""

    IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}

    def __init__(self, image_root: str | Path = "data/images/products"):
        self.image_root = Path(image_root)

    def audit(self) -> dict:
        groups: dict[str, list[str]] = defaultdict(list)
        if self.image_root.exists():
            for path in self.image_root.rglob("*"):
                if path.is_file() and path.suffix.lower() in self.IMAGE_EXTENSIONS:
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
        """Elimina solo duplicados byte-a-byte, conservando el primer archivo."""
        report = self.audit()
        removed = []
        for paths in report["duplicates"]:
            for path in sorted(paths)[1:]:
                candidate = Path(path)
                candidate.unlink()
                removed.append(path)
        report["removed"] = removed
        report["duplicate_files"] = 0
        return report

    @staticmethod
    def _hash(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as file:
            for chunk in iter(lambda: file.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()
