from __future__ import annotations

from io import BytesIO

from PIL import Image


def image_bytes(
    image_format: str = "WEBP",
    color: tuple[int, int, int] = (32, 96, 160),
) -> bytes:
    """Build a tiny, fully decodable deterministic image for tests."""
    buffer = BytesIO()
    Image.new("RGB", (8, 8), color).save(buffer, format=image_format)
    return buffer.getvalue()
