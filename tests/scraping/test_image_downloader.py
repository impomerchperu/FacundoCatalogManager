from pathlib import Path
from typing import ClassVar

import pytest

from scrapers.images.image_downloader import ImageDownloader
from scrapers.images.image_hash import ImageHash
from tests.scraping.image_test_utils import image_bytes

JPEG_BYTES = image_bytes("JPEG", (10, 20, 30))


def test_image_downloader_saves_image(
    tmp_path,
    monkeypatch,
):
    class FakeResponse:
        content = JPEG_BYTES
        headers: ClassVar[dict[str, str]] = {"Content-Type": "image/jpeg"}

        def raise_for_status(self):
            pass

    def fake_get(
        url,
        timeout,
        headers,
    ):
        return FakeResponse()

    monkeypatch.setattr(
        ImageDownloader,
        "_request",
        lambda self, url, headers: fake_get(url, self.request_timeout, headers),
    )

    downloader = ImageDownloader(
        output_dir=tmp_path,
    )

    result = downloader.download(
        "P001",
        "http://image.jpg",
    )

    file = Path(tmp_path) / "P001" / "P001-01.jpg"

    assert result == file.as_posix()
    assert file.exists()
    assert file.read_bytes() == JPEG_BYTES


def test_image_downloader_stages_image_without_overwriting_canonical_file(
    tmp_path,
    monkeypatch,
):
    class FakeResponse:
        content = JPEG_BYTES
        headers: ClassVar[dict[str, str]] = {"Content-Type": "image/jpeg"}

        def raise_for_status(self):
            pass

    monkeypatch.setattr(
        ImageDownloader,
        "_request",
        lambda self, url, headers: FakeResponse(),
    )

    staging = tmp_path / "review"
    downloader = ImageDownloader(
        output_dir=tmp_path / "products",
    )

    result = downloader.download_staged("P004", "http://image.jpg", staging)

    staged_files = list(staging.glob("P004-*.jpg"))
    assert len(staged_files) == 1
    assert Path(result).name == staged_files[0].name
    assert staged_files[0].read_bytes() == JPEG_BYTES
    assert not (tmp_path / "products" / "P004" / "P004-01.jpg").exists()


def test_image_downloader_uses_custom_http_settings(tmp_path, monkeypatch):
    calls = []

    class FakeResponse:
        content = JPEG_BYTES
        headers: ClassVar[dict[str, str]] = {"Content-Type": "image/jpeg"}

        def raise_for_status(self):
            pass

    def fake_get(url, timeout, headers):
        calls.append((url, timeout, headers))
        return FakeResponse()

    monkeypatch.setattr(
        ImageDownloader,
        "_request",
        lambda self, url, headers: fake_get(url, self.request_timeout, headers),
    )

    downloader = ImageDownloader(
        output_dir=tmp_path,
        request_timeout=7,
        max_retries=4,
    )

    downloader.download("P002", "http://image.png")

    assert calls == [
        (
            "http://image.png",
            7,
            {"User-Agent": "FacundoCatalogManager/1.0"},
        )
    ]


def test_image_downloader_retries_transient_failures(tmp_path, monkeypatch):
    calls = []

    class FakeResponse:
        content = JPEG_BYTES
        headers: ClassVar[dict[str, str]] = {"Content-Type": "image/jpeg"}

        def raise_for_status(self):
            pass

    def fake_get(url, timeout, headers):
        calls.append(1)
        if len(calls) < 3:
            raise __import__("requests").exceptions.Timeout("timeout")
        return FakeResponse()

    monkeypatch.setattr(
        ImageDownloader,
        "_request",
        lambda self, url, headers: fake_get(url, self.request_timeout, headers),
    )
    monkeypatch.setattr(
        "scrapers.images.image_downloader.time.sleep",
        lambda _seconds: None,
    )

    downloader = ImageDownloader(
        output_dir=tmp_path,
        max_retries=3,
    )

    result = downloader.download("P003", "http://image.jpg")

    assert result == (Path(tmp_path) / "P003" / "P003-01.jpg").as_posix()
    assert len(calls) == 3


def test_image_downloader_rejects_invalid_http_settings(tmp_path):
    with pytest.raises(ValueError, match="request_timeout"):
        ImageDownloader(output_dir=tmp_path, request_timeout=0)

    with pytest.raises(ValueError, match="max_retries"):
        ImageDownloader(output_dir=tmp_path, max_retries=0)


def test_image_downloader_hash_file_matches_canonical_image_hash(tmp_path):
    image_path = tmp_path / "sample.webp"
    image_path.write_bytes(b"same-image-bytes")

    assert ImageDownloader.hash_file(image_path) == ImageHash().calculate(image_path)


def test_image_downloader_hash_file_preserves_missing_file_error(tmp_path):
    missing = tmp_path / "missing.webp"

    with pytest.raises(FileNotFoundError):
        ImageDownloader.hash_file(missing)
