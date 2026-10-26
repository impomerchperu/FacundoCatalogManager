from __future__ import annotations

import os
import shutil
import uuid
from pathlib import Path

from config.runtime_paths import resolve_data_path, to_data_relative_path
from scrapers.images.image_hash import ImageHash
from scrapers.images.image_paths import IMAGE_EXTENSIONS, IMAGE_PRODUCTS_DIR
from scrapers.images.image_validation import (
    file_extension_matches,
    identify_image_file,
)


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
    expected_extension: str,
    exclude: Path | None = None,
) -> Path | None:
    excluded_path = exclude.resolve() if exclude is not None else None
    if not directory.is_dir():
        return None

    for existing in sorted(directory.iterdir()):
        if not existing.is_file() or existing.suffix.lower() not in IMAGE_EXTENSIONS:
            continue
        if excluded_path is not None and existing.resolve() == excluded_path:
            continue
        try:
            verified = identify_image_file(existing)
        except (OSError, ValueError):
            continue
        if not file_extension_matches(existing, verified["image_extension"]):
            continue
        if (
            verified["image_hash"] == expected_hash
            and verified["image_extension"] == expected_extension
        ):
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


def store_image_in_product_group(  # noqa: PLR0912
    code: object,
    source_path: str | Path,
    position: int,
    *,
    root: str | Path = IMAGE_PRODUCTS_DIR,
    deduplicate_in_group: bool = True,
) -> tuple[str, str]:
    """Store an identifiable image under a content-derived canonical extension.

    The source file is never removed or overwritten. If its suffix is wrong,
    a correctly named copy is produced and the old reference can be retired
    only after the caller persists the new path. Callers normalizing an already
    canonical gallery may disable sibling scanning because they deduplicate
    validated paths and hashes in the surrounding batch.
    """
    source = resolve_data_path(source_path)
    if not source.is_file():
        return "", ""

    product_code = safe_product_code(code)
    if not product_code:
        return "", ""

    try:
        verified = identify_image_file(source)
    except (OSError, ValueError):
        # Unidentifiable or undecodable content must not enter the catalog's
        # canonical image store.
        return "", ""

    image_hash = verified["image_hash"]
    extension = verified["image_extension"]
    target_dir = product_image_directory(product_code, root=root)
    source_suffix_matches = file_extension_matches(source, extension)

    try:
        source_is_in_group = source.resolve().parent == target_dir.resolve()
    except OSError:
        source_is_in_group = False

    if source_is_in_group and source_suffix_matches:
        if deduplicate_in_group:
            existing = _find_matching_image(
                target_dir,
                image_hash,
                expected_extension=extension,
                exclude=source,
            )
            if existing is not None:
                return to_data_relative_path(existing), image_hash
        return to_data_relative_path(source), image_hash

    target_dir.mkdir(parents=True, exist_ok=True)
    existing = _find_matching_image(
        target_dir,
        image_hash,
        expected_extension=extension,
    )
    if existing is not None:
        return to_data_relative_path(existing), image_hash

    normalized_position = max(int(position), 1)
    target = _available_target(
        target_dir,
        product_code,
        normalized_position,
        extension,
        image_hash,
    )

    # Fully materialize and decode a private temporary before publication.
    # An exception can therefore never leave a truncated canonical image.
    temporary = target_dir / (
        f".{product_code}-{normalized_position:02d}-{uuid.uuid4().hex}.tmp"
    )
    temporary_created = False
    try:
        with source.open("rb") as source_stream, temporary.open("xb") as target_stream:
            temporary_created = True
            shutil.copyfileobj(source_stream, target_stream)
        stored_temporary = identify_image_file(temporary)
        if (
            stored_temporary["image_hash"] != image_hash
            or stored_temporary["image_extension"] != extension
        ):
            return "", ""

        for _attempt in range(8):
            try:
                # Atomic, no-overwrite publication. This path is on the same
                # volume as the temporary and is never replaced if it exists.
                os.link(temporary, target)
                break
            except FileExistsError:
                existing = _find_matching_image(
                    target_dir,
                    image_hash,
                    expected_extension=extension,
                )
                if existing is not None:
                    return to_data_relative_path(existing), image_hash
                target = target_dir / (
                    f"{product_code}-{normalized_position:02d}-"
                    f"{image_hash[:8]}-{uuid.uuid4().hex[:8]}{extension}"
                )
        else:
            return "", ""

        stored = identify_image_file(target)
        if (
            stored["image_hash"] != image_hash
            or stored["image_extension"] != extension
            or not file_extension_matches(target, extension)
        ):
            # The published file was created exclusively by this call. Leave
            # retirement to the reference-checked cleanup to avoid races.
            return "", ""
    finally:
        if temporary_created:
            temporary.unlink(missing_ok=True)

    return to_data_relative_path(target), image_hash
