from pathlib import Path

from scrapers.images.image_downloader import ImageDownloader


def test_image_downloader_saves_image(
    tmp_path,
    monkeypatch,
):

    class FakeResponse:

        content = b"\xff\xd8fake-image-data"

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
