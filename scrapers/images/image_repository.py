from __future__ import annotations

from pathlib import Path

from config.runtime_paths import DATA_DIR, resolve_data_path, to_data_relative_path
from scrapers.images.image_paths import (
    IMAGE_EXTENSIONS,
    IMAGE_PRODUCTS_DIR,
    product_image_directory,
    safe_image_code,
)
from scrapers.images.image_validation import (
    file_extension_matches,
    identify_image_file,
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
    ) -> dict[str, str] | None:
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
        if grouped is None:
            grouped = self._find_in_directory(self.output_dir, safe_code, suffix)
        if grouped is None:
            return None

        # Even legacy/grouped files must pass image decoding. Storage derives
        # the canonical suffix from decoded content and never overwrites source.
        stored_path, stored_hash = store_image_in_product_group(
            safe_code,
            grouped,
            1,
            root=self.output_dir,
        )
        if stored_path and stored_hash:
            return {
                "image_path": stored_path,
                "image_hash": stored_hash,
            }
        return None

    def find_path(self, image_path: str | Path) -> dict[str, str] | None:
        """Validate the exact DB path, repairing identifiable suffix mismatches."""
        raw_path = str(image_path or "").strip()
        if not raw_path:
            return None
        candidate = resolve_data_path(raw_path)
        try:
            candidate = candidate.resolve(strict=True)
            candidate.relative_to(DATA_DIR.resolve())
        except (OSError, ValueError):
            return None
        if not candidate.is_file():
            return None

        try:
            verified = identify_image_file(candidate)
        except (OSError, ValueError):
            # Corrupt, unsupported or undecodable files are not valid cached
            # images. The caller may fetch the source again; a failed fetch
            # clears the invalid reference instead of perpetuating bad bytes.
            return None

        if file_extension_matches(candidate, verified["image_extension"]):
            return {
                "image_path": to_data_relative_path(candidate),
                "image_hash": verified["image_hash"],
            }

        # Content is valid, but its name lies about the format. Publish a
        # correctly suffixed copy; let catalog persistence happen before the
        # post-commit cleanup removes the obsolete path.
        inferred_code = self._infer_product_code(candidate)
        if not inferred_code:
            return None
        stored_path, stored_hash = store_image_in_product_group(
            inferred_code,
            candidate,
            1,
            root=self.output_dir,
        )
        if not stored_path or not stored_hash:
            return None
        return {"image_path": stored_path, "image_hash": stored_hash}

    def _infer_product_code(self, path: Path) -> str:
        """Infer a safe product folder key from supported legacy path layouts."""
        parent = path.parent.resolve()
        output_root = self.output_dir.resolve()
        if parent == output_root:
            return safe_image_code(path.stem)
        try:
            parent.relative_to(output_root)
        except ValueError:
            parts = [part.casefold() for part in path.parts]
            for folder in ("products", "gallery"):
                if folder in parts:
                    index = parts.index(folder)
                    if index + 1 < len(path.parts):
                        group = path.parts[index + 1]
                        if group.casefold().endswith(tuple(IMAGE_EXTENSIONS)):
                            return safe_image_code(Path(group).stem)
                        return safe_image_code(group)
            if path.parent.name.casefold() not in {"images", "resources"}:
                return safe_image_code(path.parent.name)
            return safe_image_code(path.stem)
        return safe_image_code(path.parent.name)

    @staticmethod
    def _find_in_directory(
        directory: Path,
        safe_code: str,
        preferred_suffix: str,
    ) -> Path | None:
        if not directory.is_dir():
            return None

        candidates: list[Path] = []
        if preferred_suffix in IMAGE_EXTENSIONS:
            candidates.extend(
                [
                    directory / f"{safe_code}-01{preferred_suffix}",
                    directory / f"{safe_code}{preferred_suffix}",
                ]
            )

        candidates.extend(
            sorted(
                path
                for path in directory.glob(f"{safe_code}-*")
                if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
            )
        )
        candidates.extend(
            sorted(
                path
                for path in directory.glob(f"{safe_code}.*")
                if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
            )
        )

        seen: set[Path] = set()
        for candidate in candidates:
            if candidate in seen or not candidate.is_file():
                continue
            seen.add(candidate)
            try:
                identify_image_file(candidate)
            except (OSError, ValueError):
                continue
            return candidate
        return None
