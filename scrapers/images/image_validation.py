from __future__ import annotations

import hashlib
import warnings
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


def identify_image_file(path: str | Path) -> dict[str, str]:
    """Identify a local image from its decoded content, independently of suffix."""
    image_path = Path(path)
    size = image_path.stat().st_size
    if size <= 0 or size > MAX_IMAGE_BYTES:
        raise ValueError("La imagen local está vacía o supera el límite de 20 MiB.")
    return identify_image_bytes(image_path.read_bytes())


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
