from __future__ import annotations

from pathlib import Path

from scrapers.images import image_validation
from tests.scraping.image_test_utils import image_bytes


def test_image_verification_cache_reuses_unchanged_file_and_returns_fresh_dict(
    tmp_path: Path,
    monkeypatch,
):
    path = tmp_path / "product.webp"
    path.write_bytes(image_bytes("WEBP"))
    original_identify = image_validation.identify_image_bytes
    calls = 0

    def counted_identify(data: bytes, content_type: str = "") -> dict[str, str]:
        nonlocal calls
        calls += 1
        return original_identify(data, content_type)

    monkeypatch.setattr(image_validation, "identify_image_bytes", counted_identify)
    image_validation.begin_image_verification_cache()
    try:
        first = image_validation.identify_image_file(path)
        first["image_hash"] = "caller mutation"
        second = image_validation.identify_image_file(path)

        assert calls == 1
        assert second["image_hash"] != "caller mutation"
        assert second["image_hash"] == original_identify(path.read_bytes())["image_hash"]

        path.write_bytes(image_bytes("WEBP", (220, 10, 20)))
        third = image_validation.identify_image_file(path)
        assert calls == 2
        assert third["image_hash"] != second["image_hash"]
    finally:
        image_validation.clear_image_verification_cache()


def test_image_verification_cache_is_scoped_to_scraping_sessions(
    tmp_path: Path,
    monkeypatch,
):
    path = tmp_path / "product.png"
    path.write_bytes(image_bytes("PNG"))
    original_identify = image_validation.identify_image_bytes
    calls = 0

    def counted_identify(data: bytes, content_type: str = "") -> dict[str, str]:
        nonlocal calls
        calls += 1
        return original_identify(data, content_type)

    monkeypatch.setattr(image_validation, "identify_image_bytes", counted_identify)
    image_validation.begin_image_verification_cache()
    image_validation.begin_image_verification_cache()
    try:
        image_validation.identify_image_file(path)
        image_validation.clear_image_verification_cache()
        image_validation.identify_image_file(path)
        assert calls == 1
    finally:
        image_validation.clear_image_verification_cache()

    image_validation.identify_image_file(path)
    assert calls == 2


def test_image_verification_retries_when_file_changes_during_read(
    tmp_path: Path,
    monkeypatch,
):
    path = tmp_path / "product.png"
    original_bytes = image_bytes("PNG")
    replacement_bytes = image_bytes("JPEG", (200, 30, 40))
    assert len(original_bytes) != len(replacement_bytes)
    path.write_bytes(original_bytes)
    original_identify = image_validation.identify_image_bytes
    calls = 0

    def replace_during_identify(data: bytes, content_type: str = "") -> dict[str, str]:
        nonlocal calls
        calls += 1
        result = original_identify(data, content_type)
        if calls == 1:
            path.write_bytes(replacement_bytes)
        return result

    monkeypatch.setattr(
        image_validation,
        "identify_image_bytes",
        replace_during_identify,
    )
    image_validation.begin_image_verification_cache()
    try:
        result = image_validation.identify_image_file(path)
        assert calls == 2
        assert result["image_extension"] == ".jpg"
        assert result["image_hash"] == original_identify(replacement_bytes)["image_hash"]
    finally:
        image_validation.clear_image_verification_cache()
