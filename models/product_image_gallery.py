from __future__ import annotations

from typing import Any


def _image_path(image: dict[str, Any]) -> str:
    return str(image.get("image_path") or image.get("path") or "").strip()


def _image_url(image: dict[str, Any]) -> str:
    return str(image.get("url") or "").strip().casefold()


def _image_hash(image: dict[str, Any]) -> str:
    return str(image.get("image_hash") or image.get("hash") or "").strip().casefold()


def normalize_product_gallery(
    product: object,
    gallery_images: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Return one ordered image list, putting the primary first and deduplicating.

    Image paths, source URLs, and content hashes are all considered identities.
    This collapses a primary image that was also saved as the first gallery item,
    including legacy records that point to two different files for the same URL
    or image hash.
    """
    source = (
        gallery_images
        if gallery_images is not None
        else list(getattr(product, "gallery_images", []) or [])
    )
    normalized: list[dict[str, Any]] = []
    for raw in source:
        if not isinstance(raw, dict):
            continue
        image = dict(raw)
        path = _image_path(image)
        if not path:
            continue
        image["image_path"] = path
        normalized.append(image)

    primary_path = str(getattr(product, "image_path", "") or "").strip()
    if primary_path:
        primary = {
            "url": str(getattr(product, "image_url", "") or "").strip(),
            "image_path": primary_path,
            "image_hash": str(getattr(product, "image_hash", "") or "").strip(),
            "position": 1,
            "source": "primary",
        }
        primary_url = _image_url(primary)
        primary_hash = _image_hash(primary)
        match_index = next(
            (
                index
                for index, image in enumerate(normalized)
                if _image_path(image).casefold() == primary_path.casefold()
                or (
                    primary_url
                    and _image_url(image) == primary_url
                )
                or (
                    primary_hash
                    and _image_hash(image) == primary_hash
                )
            ),
            None,
        )
        if match_index is not None:
            matched = normalized.pop(match_index)
            primary.update(
                {
                    key: value
                    for key, value in matched.items()
                    if key not in {"image_path", "url", "image_hash", "position"}
                    and key not in primary
                }
            )
        normalized.insert(0, primary)

    result: list[dict[str, Any]] = []
    seen_paths: set[str] = set()
    seen_urls: set[str] = set()
    seen_hashes: set[str] = set()
    for image in normalized:
        path = _image_path(image)
        url = _image_url(image)
        image_hash = _image_hash(image)
        if not path:
            continue
        path_key = path.replace("\\", "/").casefold()
        if (
            path_key in seen_paths
            or (url and url in seen_urls)
            or (image_hash and image_hash in seen_hashes)
        ):
            continue
        seen_paths.add(path_key)
        if url:
            seen_urls.add(url)
        if image_hash:
            seen_hashes.add(image_hash)
        image["image_path"] = path
        image["position"] = len(result) + 1
        result.append(image)

    return result
