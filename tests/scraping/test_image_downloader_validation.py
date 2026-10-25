from pathlib import Path
from typing import ClassVar

from scrapers.images.image_downloader import ImageDownloader
from scrapers.images.image_validation import identify_image_file
from tests.scraping.image_test_utils import image_bytes

JPEG_BYTES = image_bytes("JPEG", (10, 20, 30))


class FakeResponse:
    content = JPEG_BYTES
    headers: ClassVar[dict[str, str]] = {"Content-Type": "image/jpeg"}

    def raise_for_status(self):
        return None


def test_image_downloader_saves_image_with_canonical_code_name(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(
        ImageDownloader, "_request", lambda self, url, headers: FakeResponse()
    )

    downloader = ImageDownloader(
        output_dir=tmp_path,
        request_timeout=5,
        max_retries=1,
    )

    result = downloader.download("P002", "http://image.example/product")

    expected = Path(tmp_path) / "P002" / "P002-01.jpg"
    assert result == expected.as_posix()
    assert expected.read_bytes() == FakeResponse.content


def test_image_downloader_sanitizes_code_before_writing_file(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(
        ImageDownloader, "_request", lambda self, url, headers: FakeResponse()
    )

    downloader = ImageDownloader(
        output_dir=tmp_path,
        request_timeout=5,
        max_retries=1,
    )

    result = downloader.download("P 003/TEST", "http://image.example/product")

    expected = Path(tmp_path) / "P_003_TEST" / "P_003_TEST-01.jpg"
    assert result == expected.as_posix()
    assert expected.exists()


def test_image_downloader_uses_decoded_format_instead_of_url_suffix(
    tmp_path,
    monkeypatch,
):
    class PngResponse:
        content = image_bytes("PNG", (23, 45, 67))
        headers: ClassVar[dict[str, str]] = {"Content-Type": "image/webp"}

        def raise_for_status(self):
            return None

    monkeypatch.setattr(
        ImageDownloader,
        "_request",
        lambda self, url, headers: PngResponse(),
    )
    downloader = ImageDownloader(output_dir=tmp_path, max_retries=1)

    result = downloader.download(
        "SKB05J4",
        "https://example.test/SKB05J4.webp",
    )

    expected = tmp_path / "SKB05J4" / "SKB05J4-01.png"
    assert Path(result) == expected
    assert expected.is_file()
    assert identify_image_file(expected)["image_extension"] == ".png"
