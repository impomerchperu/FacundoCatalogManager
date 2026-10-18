from __future__ import annotations

import shutil
from pathlib import Path

from config.runtime_paths import resolve_data_path, to_data_relative_path
from scrapers.images.image_hash import ImageHash
from scrapers.images.image_paths import IMAGE_EXTENSIONS, IMAGE_PRODUCTS_DIR


def safe_product_code(code: object) -> str:
    """Normalize a product code for use in a filesystem path."""
    value = str(code or "").strip()
    return "".join(
        character if character.isalnum() or character in "-_" else "_"
        for character in value
    )


def product_image_directory(
    code: object,
    *,
    root: str | Path = IMAGE_PRODUCTS_DIR,
) -> Path:
    """Return the canonical folder that holds every image for one product."""
    return resolve_data_path(root) / safe_product_code(code)


def _find_matching_image(
    directory: Path,
    expected_hash: str,
    *,
    exclude: Path | None = None,
) -> Path | None:
    excluded_path = exclude.resolve() if exclude is not None else None
    for existing in sorted(directory.iterdir()):
        if not existing.is_file() or existing.suffix.lower() not in IMAGE_EXTENSIONS:
            continue
        if excluded_path is not None and existing.resolve() == excluded_path:
            continue
        if ImageHash().calculate(existing) == expected_hash:
            return existing
    return None


def _available_target(
    directory: Path,
    code: str,
    position: int,
    extension: str,
    image_hash: str,
) -> Path:
    target = directory / f"{code}-{position:02d}{extension}"
    if target.is_file():
        if ImageHash().calculate(target) == image_hash:
            return target
        target = directory / f"{code}-{position:02d}-{image_hash[:8]}{extension}"

    collision_index = 1
    while target.exists() and ImageHash().calculate(target) != image_hash:
        target = directory / (
            f"{code}-{position:02d}-{image_hash[:8]}-{collision_index}{extension}"
        )
        collision_index += 1
    return target


def store_image_in_product_group(
    code: object,
    source_path: str | Path,
    position: int,
    *,
    root: str | Path = IMAGE_PRODUCTS_DIR,
) -> tuple[str, str]:
    """Copy an image into a product's canonical folder without clobbering files.

    Images with identical content within one product group reuse one stored
    file. A source already inside the canonical folder is reused as-is.
    """
    source = resolve_data_path(source_path)
    if not source.is_file():
        return "", ""

    product_code = safe_product_code(code)
    if not product_code:
        return "", ""

    target_dir = product_image_directory(product_code, root=root)
    image_hash = ImageHash().calculate(source)
    try:
        if source.resolve().parent == target_dir.resolve():
            existing = _find_matching_image(
                target_dir,
                image_hash,
                exclude=source,
            )
            if existing is not None:
                return to_data_relative_path(existing), image_hash
            return to_data_relative_path(source), image_hash
    except OSError:
        pass

    extension = source.suffix.lower()
    if extension not in IMAGE_EXTENSIONS:
        extension = ".webp"

    target_dir.mkdir(parents=True, exist_ok=True)
    existing = _find_matching_image(target_dir, image_hash)
    if existing is not None:
        return to_data_relative_path(existing), image_hash

    target = _available_target(
        target_dir,
        product_code,
        max(int(position), 1),
        extension,
        image_hash,
    )
    if not target.exists():
        shutil.copy2(source, target)

    return to_data_relative_path(target), image_hash
