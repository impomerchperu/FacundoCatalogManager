from pathlib import Path
from typing import ClassVar

import requests

from scrapers.images.image_downloader import ImageDownloader


class FakeResponse:
    content = b"image-data"
    headers: ClassVar[dict[str, str]] = {"Content-Type": "image/jpeg"}

    def raise_for_status(self):
        return None


def test_image_downloader_saves_image_with_canonical_code_name(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(requests, "get", lambda *args, **kwargs: FakeResponse())

    downloader = ImageDownloader(
        output_dir=tmp_path,
        request_timeout=5,
        max_retries=1,
    )

    result = downloader.download("P002", "http://image.example/product")

    expected = Path(tmp_path) / "P002.jpg"
    assert result == expected.as_posix()
    assert expected.read_bytes() == b"image-data"


def test_image_downloader_sanitizes_code_before_writing_file(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(requests, "get", lambda *args, **kwargs: FakeResponse())

    downloader = ImageDownloader(
        output_dir=tmp_path,
        request_timeout=5,
        max_retries=1,
    )

    result = downloader.download("P 003/TEST", "http://image.example/product")

    expected = Path(tmp_path) / "P_003_TEST.jpg"
    assert result == expected.as_posix()
    assert expected.exists()
