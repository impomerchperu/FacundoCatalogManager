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


def store_image_in_product_group(
    code: object,
    source_path: str | Path,
    position: int,
    *,
    root: str | Path = IMAGE_PRODUCTS_DIR,
) -> tuple[str, str]:
    """Copy an image into a product's canonical folder without clobbering files.

    A source already inside the canonical product folder is reused. Legacy
    images are copied to a stable position-based filename. If that filename
    contains different content, a hash suffix avoids overwriting it.
    """
    source = resolve_data_path(source_path)
    if not source.is_file():
        return "", ""

    product_code = safe_product_code(code)
    if not product_code:
        return "", ""

    target_dir = product_image_directory(product_code, root=root)
    try:
        if source.resolve().parent == target_dir.resolve():
            return (
                to_data_relative_path(source),
                ImageHash().calculate(source),
            )
    except OSError:
        pass

    image_hash = ImageHash().calculate(source)
    extension = source.suffix.lower()
    if extension not in IMAGE_EXTENSIONS:
        extension = ".webp"

    target_dir.mkdir(parents=True, exist_ok=True)
    for existing in sorted(target_dir.iterdir()):
        if not existing.is_file() or existing.suffix.lower() not in IMAGE_EXTENSIONS:
            continue
        if ImageHash().calculate(existing) == image_hash:
            return to_data_relative_path(existing), image_hash

    target = target_dir / f"{product_code}-{max(int(position), 1):02d}{extension}"
    if target.is_file():
        if ImageHash().calculate(target) == image_hash:
            return to_data_relative_path(target), image_hash
        target = target_dir / (
            f"{product_code}-{max(int(position), 1):02d}-{image_hash[:8]}{extension}"
        )

    collision_index = 1
    while target.exists() and ImageHash().calculate(target) != image_hash:
        target = target_dir / (
            f"{product_code}-{max(int(position), 1):02d}-"
            f"{image_hash[:8]}-{collision_index}{extension}"
        )
        collision_index += 1

    if not target.exists():
        shutil.copy2(source, target)

    return to_data_relative_path(target), image_hash
