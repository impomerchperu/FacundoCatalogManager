from __future__ import annotations

from pathlib import Path

from config.runtime_paths import resolve_data_path, to_data_relative_path
from scrapers.images.image_downloader import ImageDownloader
from scrapers.images.image_paths import (
    IMAGE_EXTENSIONS,
    IMAGE_PRODUCTS_DIR,
    product_image_directory,
    safe_image_code,
)
from scrapers.images.product_image_storage import store_image_in_product_group


class ImageRepository:
    """Find canonical product images and migrate legacy primaries by copying."""

    def __init__(self, output_dir: str | Path = IMAGE_PRODUCTS_DIR):
        self.output_dir = resolve_data_path(output_dir)

    def find(
        self,
        code: str,
        image_url: str | None = None,
    ) -> dict | None:
        safe_code = safe_image_code(code)
        if not safe_code:
            return None

        suffix = (
            Path(image_url.split("?", 1)[0]).suffix.lower()
            if image_url
            else ""
        )
        group_dir = product_image_directory(
            safe_code,
            root=self.output_dir,
        )
        grouped = self._find_in_directory(group_dir, safe_code, suffix)
        if grouped is not None:
            return self._image_record(grouped)

        legacy = self._find_in_directory(self.output_dir, safe_code, suffix)
        if legacy is None:
            return None

        # Keep the legacy source untouched until the caller persists the new
        # database reference. The cleanup tool can remove the orphan later.
        stored_path, stored_hash = store_image_in_product_group(
            safe_code,
            legacy,
            1,
            root=self.output_dir,
        )
        if stored_path:
            return {
                "image_path": stored_path,
                "image_hash": stored_hash,
            }
        return self._image_record(legacy)

    def find_path(self, image_path: str | Path) -> dict | None:
        """Resolve exactly the image referenced by the catalog, not an older sibling."""
        raw_path = str(image_path or "").strip()
        if not raw_path:
            return None
        candidate = resolve_data_path(raw_path)
        try:
            candidate = candidate.resolve(strict=True)
            candidate.relative_to(self.output_dir.parent.parent.resolve())
        except (OSError, ValueError):
            return None
        if not candidate.is_file() or candidate.suffix.lower() not in IMAGE_EXTENSIONS:
            return None
        return self._image_record(candidate)

    @staticmethod
    def _find_in_directory(
        directory: Path,
        safe_code: str,
        preferred_suffix: str,
    ) -> Path | None:
        if not directory.is_dir():
            return None

        if preferred_suffix in IMAGE_EXTENSIONS:
            preferred = directory / f"{safe_code}-01{preferred_suffix}"
            if preferred.is_file():
                return preferred
            legacy_preferred = directory / f"{safe_code}{preferred_suffix}"
            if legacy_preferred.is_file():
                return legacy_preferred

        grouped_matches = sorted(
            path
            for path in directory.glob(f"{safe_code}-*")
            if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
        )
        if grouped_matches:
            return grouped_matches[0]

        legacy_matches = sorted(
            path
            for path in directory.glob(f"{safe_code}.*")
            if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
        )
        return legacy_matches[0] if legacy_matches else None

    @staticmethod
    def _image_record(path: Path) -> dict[str, str]:
        return {
            "image_path": to_data_relative_path(path),
            "image_hash": ImageDownloader.hash_file(path),
        }
