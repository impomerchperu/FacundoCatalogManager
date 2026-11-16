from __future__ import annotations

import hashlib
import threading
import warnings
from functools import lru_cache
from io import BytesIO
from pathlib import Path

from PIL import Image

MAX_IMAGE_BYTES = 20 * 1024 * 1024

_FORMAT_EXTENSIONS = {
    "JPEG": ".jpg",
    "PNG": ".png",
    "WEBP": ".webp",
    "GIF": ".gif",
}

_VERIFICATION_CACHE_LOCK = threading.Lock()
_VERIFICATION_CACHE_SESSIONS = 0


class _ImageChangedDuringVerification(OSError):
    """The file identity changed while a cached verification was in progress."""



def identify_image_bytes(
    data: bytes,
    content_type: str = "",
) -> dict[str, str]:
    """Decode and identify a supported raster image before accepting its bytes."""
    if not data or len(data) > MAX_IMAGE_BYTES:
        raise ValueError("La imagen está vacía o supera el límite de 20 MiB.")

    image_format = ""
    consistent_format = False
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(data)) as image:
                image_format = str(image.format or "").upper()
                if image_format in _FORMAT_EXTENSIONS:
                    image.verify()

            # verify() checks container integrity; load() confirms the image
            # decoder can actually read pixel data before the bytes are stored.
            if image_format in _FORMAT_EXTENSIONS:
                with Image.open(BytesIO(data)) as image:
                    consistent_format = (
                        str(image.format or "").upper() == image_format
                    )
                    if consistent_format:
                        image.load()
    except Exception as error:
        # Raster decoders can raise format-specific errors (including EOFError
        # and struct errors) for truncated or malformed files. Treat any such
        # decoder failure as an unidentified image, not as a cacheable object.
        raise ValueError(
            "La respuesta no contiene una imagen raster válida o identificable."
        ) from error

    if image_format not in _FORMAT_EXTENSIONS:
        raise ValueError("El formato de imagen no es compatible.")
    if not consistent_format:
        raise ValueError("El formato de imagen es inconsistente.")

    # Content-Type is advisory only; decoded bytes determine the real format.
    del content_type

    return {
        "image_extension": _FORMAT_EXTENSIONS[image_format],
        "image_format": image_format,
        "image_hash": hashlib.sha256(data).hexdigest(),
    }


@lru_cache(maxsize=4096)
def _identify_image_file_cached(
    resolved_path: str,
    device: int,
    inode: int,
    size: int,
    modified_ns: int,
    changed_ns: int,
) -> tuple[str, str, str]:
    """Decode one unchanged file and cache only its immutable verification result."""
    image_path = Path(resolved_path)
    before = image_path.stat()
    before_fingerprint = (
        before.st_dev,
        before.st_ino,
        before.st_size,
        before.st_mtime_ns,
        before.st_ctime_ns,
    )
    if before_fingerprint != (device, inode, size, modified_ns, changed_ns):
        raise _ImageChangedDuringVerification(
            "La imagen cambió antes de completar su validación."
        )
    if size <= 0 or size > MAX_IMAGE_BYTES:
        raise ValueError("La imagen local está vacía o supera el límite de 20 MiB.")

    verified = identify_image_bytes(image_path.read_bytes())
    after = image_path.stat()
    after_fingerprint = (
        after.st_dev,
        after.st_ino,
        after.st_size,
        after.st_mtime_ns,
        after.st_ctime_ns,
    )
    if after_fingerprint != before_fingerprint:
        raise _ImageChangedDuringVerification(
            "La imagen cambió durante su validación."
        )
    return (
        verified["image_extension"],
        verified["image_format"],
        verified["image_hash"],
    )


def identify_image_file(path: str | Path) -> dict[str, str]:
    """Identify a local image from its decoded content, independently of suffix."""
    image_path = Path(path)
    with _VERIFICATION_CACHE_LOCK:
        cache_enabled = _VERIFICATION_CACHE_SESSIONS > 0
    if not cache_enabled:
        size = image_path.stat().st_size
        if size <= 0 or size > MAX_IMAGE_BYTES:
            raise ValueError("La imagen local está vacía o supera el límite de 20 MiB.")
        return identify_image_bytes(image_path.read_bytes())

    for attempt in range(2):
        image_path = image_path.resolve(strict=True)
        stat = image_path.stat()
        size = stat.st_size
        try:
            extension, image_format, image_hash = _identify_image_file_cached(
                str(image_path),
                stat.st_dev,
                stat.st_ino,
                size,
                stat.st_mtime_ns,
                stat.st_ctime_ns,
            )
        except _ImageChangedDuringVerification:
            if attempt == 0:
                continue
            raise
        # Return a fresh mapping so a caller cannot mutate a later cached result.
        return {
            "image_extension": extension,
            "image_format": image_format,
            "image_hash": image_hash,
        }

    raise AssertionError("La verificación de la imagen terminó sin resultado.")


def begin_image_verification_cache() -> None:
    """Enable shared file-verification reuse for one or more active scrapes."""
    global _VERIFICATION_CACHE_SESSIONS
    with _VERIFICATION_CACHE_LOCK:
        if _VERIFICATION_CACHE_SESSIONS == 0:
            _identify_image_file_cached.cache_clear()
        _VERIFICATION_CACHE_SESSIONS += 1


def clear_image_verification_cache() -> None:
    """End one scrape's reuse window and drop entries after the final session."""
    global _VERIFICATION_CACHE_SESSIONS
    with _VERIFICATION_CACHE_LOCK:
        if _VERIFICATION_CACHE_SESSIONS > 0:
            _VERIFICATION_CACHE_SESSIONS -= 1
        if _VERIFICATION_CACHE_SESSIONS == 0:
            _identify_image_file_cached.cache_clear()


def file_extension_matches(path: str | Path, actual_extension: str) -> bool:
    """Return whether a filename suffix correctly identifies its decoded format."""
    suffix = Path(path).suffix.lower()
    if actual_extension == ".jpg" and suffix == ".jpeg":
        return True
    return suffix == actual_extension


def is_identifiable_image_file(path: str | Path) -> bool:
    """Best-effort content detection for cleanup of image files with unusual suffixes."""
    try:
        identify_image_file(path)
    except (OSError, ValueError):
        return False
    return True
