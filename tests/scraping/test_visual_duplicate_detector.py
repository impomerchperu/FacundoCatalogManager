from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

from scrapers.images.visual_duplicate_detector import (
    build_visual_fingerprint,
    is_generated_resolution_duplicate,
)


def _pattern_image(size: int, *, color: str = "royalblue") -> Image.Image:
    image = Image.new("RGB", (size, size), "white")
    draw = ImageDraw.Draw(image)
    margin = max(size // 12, 2)
    draw.rectangle(
        (margin, margin, size - margin, size - margin),
        outline=color,
        width=max(size // 40, 1),
    )
    draw.ellipse(
        (size // 4, size // 4, size * 3 // 4, size * 3 // 4),
        fill=color,
    )
    draw.line(
        (margin, size // 2, size - margin, size // 2),
        fill="gold",
        width=max(size // 30, 1),
    )
    return image


def _save_webp(image: Image.Image, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, format="WEBP", quality=94, method=6)


def test_generated_scaled_variant_is_detected_by_visual_content(
    tmp_path: Path,
):
    original_path = tmp_path / "original.webp"
    scaled_path = tmp_path / "scaled.webp"

    original = _pattern_image(512)
    _save_webp(original, original_path)
    _save_webp(original.resize((320, 320), Image.Resampling.LANCZOS), scaled_path)

    original_fp = build_visual_fingerprint(
        original_path,
        "https://site.test/uploads/FB-1507-2.webp",
    )
    scaled_fp = build_visual_fingerprint(
        scaled_path,
        "https://site.test/uploads/FB-1507-2-scaled.webp",
    )

    assert original_fp is not None
    assert scaled_fp is not None
    assert original_fp.area > scaled_fp.area
    assert is_generated_resolution_duplicate(original_fp, scaled_fp)


def test_similar_images_from_different_url_families_are_not_auto_removed(
    tmp_path: Path,
):
    primary_path = tmp_path / "primary.webp"
    alternate_path = tmp_path / "alternate.webp"

    source = _pattern_image(512)
    _save_webp(source, primary_path)
    _save_webp(source.resize((320, 320), Image.Resampling.LANCZOS), alternate_path)

    primary = build_visual_fingerprint(
        primary_path,
        "https://site.test/uploads/FB-1507-2.webp",
    )
    alternate = build_visual_fingerprint(
        alternate_path,
        "https://site.test/uploads/FB-1507-side.webp",
    )

    assert primary is not None
    assert alternate is not None
    assert not is_generated_resolution_duplicate(primary, alternate)


def test_different_image_in_same_generated_variant_family_is_preserved(
    tmp_path: Path,
):
    primary_path = tmp_path / "primary.webp"
    wrong_variant_path = tmp_path / "wrong-variant.webp"

    _save_webp(_pattern_image(512, color="royalblue"), primary_path)
    _save_webp(_pattern_image(320, color="crimson"), wrong_variant_path)

    primary = build_visual_fingerprint(
        primary_path,
        "https://site.test/uploads/product.webp",
    )
    wrong_variant = build_visual_fingerprint(
        wrong_variant_path,
        "https://site.test/uploads/product-scaled.webp",
    )

    assert primary is not None
    assert wrong_variant is not None
    assert not is_generated_resolution_duplicate(primary, wrong_variant)


def test_missing_or_unreadable_image_fails_open(tmp_path: Path):
    missing = build_visual_fingerprint(
        tmp_path / "missing.webp",
        "https://site.test/uploads/product.webp",
    )

    assert missing is None
    assert not is_generated_resolution_duplicate(missing, None)
