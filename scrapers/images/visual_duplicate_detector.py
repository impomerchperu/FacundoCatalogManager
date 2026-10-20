from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from re import IGNORECASE
from re import compile as re_compile
from urllib.parse import unquote, urlsplit

from PIL import Image, ImageChops, ImageOps, ImageStat

_CANVAS_SIZE = 128
_MAX_DHASH_DISTANCE = 4
_MAX_NORMALIZED_PIXEL_DIFFERENCE = 1.0
_MAX_ASPECT_RATIO_DIFFERENCE = 0.005
_MIN_AREA_DIFFERENCE = 0.02
_VARIANT_SUFFIX = re_compile(r"-(?:scaled|\d{2,4}x\d{2,4})$", IGNORECASE)


@dataclass(frozen=True)
class VisualImageFingerprint:
    """Small, decoded fingerprint used only to detect generated image variants."""

    path: Path
    url_family: tuple[str, str, str] | None
    has_generated_variant_suffix: bool
    width: int
    height: int
    dhash: int
    canvas: Image.Image

    @property
    def area(self) -> int:
        return self.width * self.height


def _url_family(url: str) -> tuple[tuple[str, str, str] | None, bool]:
    """Return a CMS variant family, ignoring query strings and image extensions."""
    raw_url = str(url or "").strip()
    parts = urlsplit(raw_url)
    if not parts.scheme or not parts.netloc or not parts.path:
        return None, False

    decoded_path = unquote(parts.path).replace("\\", "/")
    filename = PurePosixPath(decoded_path).name
    suffix = PurePosixPath(filename).suffix
    stem = filename[: -len(suffix)] if suffix else filename
    has_variant_suffix = False

    while True:
        normalized = _VARIANT_SUFFIX.sub("", stem)
        if normalized == stem:
            break
        has_variant_suffix = True
        stem = normalized

    if not stem:
        return None, has_variant_suffix

    family = (
        parts.netloc.casefold(),
        str(PurePosixPath(decoded_path).parent).casefold(),
        stem.casefold(),
    )
    return family, has_variant_suffix


def build_visual_fingerprint(
    path: str | Path,
    url: str = "",
) -> VisualImageFingerprint | None:
    """Decode a local raster image into a cheap perceptual comparison canvas.

    Invalid/unavailable files return None so callers fail open and preserve the
    candidate instead of accidentally dropping a valid alternative.
    """
    image_path = Path(path)
    try:
        with Image.open(image_path) as source:
            oriented = ImageOps.exif_transpose(source)
            width, height = oriented.size
            if width <= 0 or height <= 0:
                return None

            oriented.thumbnail(
                (_CANVAS_SIZE, _CANVAS_SIZE),
                Image.Resampling.LANCZOS,
            )
            rgba = oriented.convert("RGBA")
            background = Image.new("RGBA", rgba.size, "white")
            background.alpha_composite(rgba)
            rgb = background.convert("RGB")

            canvas = Image.new("RGB", (_CANVAS_SIZE, _CANVAS_SIZE), "white")
            canvas.paste(
                rgb,
                (
                    (_CANVAS_SIZE - rgb.width) // 2,
                    (_CANVAS_SIZE - rgb.height) // 2,
                ),
            )

        grayscale = canvas.convert("L").resize((9, 8), Image.Resampling.LANCZOS)
        # Pillow types ImagingCore inconsistently; bytes returns the grayscale
        # pixel values as ints and avoids that typing mismatch.
        pixels = list(grayscale.tobytes())
        perceptual_hash = 0
        for y in range(8):
            for x in range(8):
                perceptual_hash = (
                    (perceptual_hash << 1)
                    | int(pixels[y * 9 + x] > pixels[y * 9 + x + 1])
                )

        family, has_variant_suffix = _url_family(url)
        return VisualImageFingerprint(
            path=image_path.resolve(),
            url_family=family,
            has_generated_variant_suffix=has_variant_suffix,
            width=width,
            height=height,
            dhash=perceptual_hash,
            canvas=canvas,
        )
    except Exception:  # noqa: BLE001
        # Image decoders raise format-specific exceptions for corrupt legacy
        # files. A failed fingerprint must preserve the candidate.
        return None


def is_generated_resolution_duplicate(
    accepted: VisualImageFingerprint | None,
    candidate: VisualImageFingerprint | None,
) -> bool:
    """Return True only for high-confidence CMS size variants of one source.

    Similar-looking product photos are deliberately not enough. The URLs must
    identify the same image family, at least one must have a CMS-generated
    size suffix, aspect ratios must match, resolutions must differ, and both
    perceptual and normalized pixel metrics must be strict.
    """
    if accepted is None or candidate is None:
        return False
    if not (
        accepted.url_family
        and accepted.url_family == candidate.url_family
        and (
            accepted.has_generated_variant_suffix
            or candidate.has_generated_variant_suffix
        )
    ):
        return False

    max_area = max(accepted.area, candidate.area)
    min_area = min(accepted.area, candidate.area)
    if max_area <= 0 or (max_area - min_area) / max_area < _MIN_AREA_DIFFERENCE:
        return False

    accepted_aspect = accepted.width / accepted.height
    candidate_aspect = candidate.width / candidate.height
    aspect_delta = abs(accepted_aspect - candidate_aspect) / max(
        accepted_aspect, candidate_aspect, 1e-9
    )
    if aspect_delta > _MAX_ASPECT_RATIO_DIFFERENCE:
        return False

    if (accepted.dhash ^ candidate.dhash).bit_count() > _MAX_DHASH_DISTANCE:
        return False

    difference = ImageChops.difference(accepted.canvas, candidate.canvas)
    normalized_difference = (
        sum(ImageStat.Stat(difference).mean) / 3 / 255 * 100
    )
    return normalized_difference <= _MAX_NORMALIZED_PIXEL_DIFFERENCE
