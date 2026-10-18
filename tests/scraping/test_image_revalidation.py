from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from scrapers.images.image_downloader import ImageDownloader
from tests.scraping.image_test_utils import image_bytes

JPEG_OLD = image_bytes("JPEG", (10, 20, 30))
JPEG_NEW = image_bytes("JPEG", (200, 180, 160))


class FakeResponse:
    def __init__(self, *, status_code=200, content=b"", headers=None, url="https://example.test/image.jpg"):
        self.status_code = status_code
        self.content = content
        self.headers = headers or {}
        self.url = url

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"unexpected status {self.status_code}")

    def close(self):
        pass


def test_revalidate_primary_uses_etag_and_keeps_local_bytes_on_304(tmp_path, monkeypatch):
    image = tmp_path / "P100" / "P100-01.jpg"
    image.parent.mkdir(parents=True)
    image.write_bytes(JPEG_OLD)
    calls = []

    def fake_request(self, url, headers):
        calls.append((url, dict(headers)))
        return FakeResponse(
            status_code=304,
            headers={"ETag": '"revision-1"'},
            url=url,
        )

    monkeypatch.setattr(ImageDownloader, "_request", fake_request)
    downloader = ImageDownloader(output_dir=tmp_path)
    expected_hash = hashlib.sha256(JPEG_OLD).hexdigest()

    result = downloader.revalidate_primary(
        "P100",
        "https://example.test/image.jpg",
        current_path=str(image),
        current_hash=expected_hash,
        etag='"revision-1"',
    )

    assert result["status"] == "not_modified"
    assert result["image_path"] == image.as_posix()
    assert result["image_hash"] == expected_hash
    assert calls[0][1]["If-None-Match"] == '"revision-1"'
    assert image.read_bytes() == JPEG_OLD


def test_revalidate_primary_versions_changed_bytes_without_overwriting_active_file(
    tmp_path,
    monkeypatch,
):
    image = tmp_path / "P101" / "P101-01.jpg"
    image.parent.mkdir(parents=True)
    image.write_bytes(JPEG_OLD)

    monkeypatch.setattr(
        ImageDownloader,
        "_request",
        lambda self, url, headers: FakeResponse(
            content=JPEG_NEW,
            headers={"Content-Type": "image/jpeg", "ETag": '"revision-2"'},
            url=url,
        ),
    )
    downloader = ImageDownloader(output_dir=tmp_path)

    result = downloader.revalidate_primary(
        "P101",
        "https://example.test/image.jpg",
        current_path=str(image),
        current_hash=hashlib.sha256(JPEG_OLD).hexdigest(),
        etag='"revision-1"',
    )

    new_path = Path(str(result["image_path"]))
    assert result["status"] == "downloaded"
    assert new_path != image
    assert new_path.is_file()
    assert hashlib.sha256(new_path.read_bytes()).hexdigest() == result["image_hash"]
    assert image.read_bytes() == JPEG_OLD
    assert result["image_etag"] == '"revision-2"'


def test_revalidate_primary_does_not_forward_validators_after_redirect(
    tmp_path,
    monkeypatch,
):
    image = tmp_path / "P104" / "P104-01.jpg"
    image.parent.mkdir(parents=True)
    image.write_bytes(JPEG_OLD)
    calls = []

    def fake_request(self, url, headers):
        calls.append((url, dict(headers)))
        if len(calls) == 1:
            return FakeResponse(
                status_code=302,
                headers={"Location": "https://cdn.example.test/image.jpg"},
                url=url,
            )
        return FakeResponse(
            content=JPEG_NEW,
            headers={"Content-Type": "image/jpeg", "ETag": '"revision-2"'},
            url=url,
        )

    monkeypatch.setattr(ImageDownloader, "_request", fake_request)
    downloader = ImageDownloader(output_dir=tmp_path)
    current_hash = hashlib.sha256(JPEG_OLD).hexdigest()

    result = downloader.revalidate_primary(
        "P104",
        "https://origin.example.test/image.jpg",
        current_path=str(image),
        current_hash=current_hash,
        etag='"revision-1"',
        last_modified="Sun, 18 Oct 2026 00:00:00 GMT",
    )

    assert calls[0][1]["If-None-Match"] == '"revision-1"'
    assert calls[0][1]["If-Modified-Since"] == "Sun, 18 Oct 2026 00:00:00 GMT"
    assert "If-None-Match" not in calls[1][1]
    assert "If-Modified-Since" not in calls[1][1]
    assert result["status"] == "downloaded"
    assert result["image_hash"] == hashlib.sha256(JPEG_NEW).hexdigest()
    assert image.read_bytes() == JPEG_OLD


def test_verify_image_file_checks_signature_extension_and_hash(tmp_path):
    valid = tmp_path / "sample.jpg"
    valid.write_bytes(JPEG_OLD)
    verified = ImageDownloader.verify_image_file(valid)
    assert verified["image_extension"] == ".jpg"
    assert verified["image_hash"] == hashlib.sha256(JPEG_OLD).hexdigest()

    mislabeled = tmp_path / "sample.webp"
    mislabeled.write_bytes(JPEG_OLD)
    with pytest.raises(ValueError, match="extensión local no coincide"):
        ImageDownloader.verify_image_file(mislabeled)


def test_downloader_rejects_private_hosts_and_redirects_before_following(tmp_path, monkeypatch):
    for url in (
        "http://127.0.0.1/image.jpg",
        "http://localhost/image.jpg",
        "https://[::1]/image.jpg",
    ):
        with pytest.raises(ValueError, match="URL de imagen"):
            ImageDownloader._validate_url(url)

    calls = []

    def fake_request(self, url, headers):
        calls.append(url)
        return FakeResponse(
            status_code=302,
            headers={"Location": "http://127.0.0.1/internal.jpg"},
            url=url,
        )

    monkeypatch.setattr(ImageDownloader, "_request", fake_request)
    downloader = ImageDownloader(output_dir=tmp_path)
    with pytest.raises(ValueError):
        downloader.download_result("P103", "https://example.test/image.jpg")

    assert calls == ["https://example.test/image.jpg"]


def test_downloader_rejects_html_disguised_as_an_image(tmp_path, monkeypatch):
    monkeypatch.setattr(
        ImageDownloader,
        "_request",
        lambda self, url, headers: FakeResponse(
            content=b"<html>not an image</html>",
            headers={"Content-Type": "image/jpeg"},
            url=url,
        ),
    )
    downloader = ImageDownloader(output_dir=tmp_path)

    with pytest.raises(ValueError, match="imagen raster"):
        downloader.download_result("P102", "https://example.test/image.jpg")

    assert not list(tmp_path.rglob("*.jpg"))
