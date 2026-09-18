from pathlib import Path
from typing import ClassVar

import pytest

from scrapers.images.image_downloader import ImageDownloader


def test_image_downloader_saves_image(
    tmp_path,
    monkeypatch,
):
    class FakeResponse:
        content = b"\xff\xd8fake-image-data"
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
        "scrapers.images.image_downloader.requests.get",
        fake_get,
    )

    downloader = ImageDownloader(
        output_dir=tmp_path,
    )

    result = downloader.download(
        "P001",
        "http://image.jpg",
    )

    file = Path(tmp_path) / "P001.jpg"

    assert result == file.as_posix()
    assert file.exists()
    assert file.read_bytes() == b"\xff\xd8fake-image-data"


def test_image_downloader_uses_custom_http_settings(tmp_path, monkeypatch):
    calls = []

    class FakeResponse:
        content = b"fake-image-data"
        headers: ClassVar[dict[str, str]] = {"Content-Type": "image/png"}

        def raise_for_status(self):
            pass

    def fake_get(url, timeout, headers):
        calls.append((url, timeout, headers))
        return FakeResponse()

    monkeypatch.setattr(
        "scrapers.images.image_downloader.requests.get",
        fake_get,
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
        content = b"fake-image-data"
        headers: ClassVar[dict[str, str]] = {"Content-Type": "image/jpeg"}

        def raise_for_status(self):
            pass

    def fake_get(url, timeout, headers):
        calls.append(1)
        if len(calls) < 3:
            raise __import__("requests").exceptions.Timeout("timeout")
        return FakeResponse()

    monkeypatch.setattr(
        "scrapers.images.image_downloader.requests.get",
        fake_get,
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

    assert result == (Path(tmp_path) / "P003.jpg").as_posix()
    assert len(calls) == 3


def test_image_downloader_rejects_invalid_http_settings(tmp_path):
    with pytest.raises(ValueError, match="request_timeout"):
        ImageDownloader(output_dir=tmp_path, request_timeout=0)

    with pytest.raises(ValueError, match="max_retries"):
        ImageDownloader(output_dir=tmp_path, max_retries=0)
