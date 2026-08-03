from utils.scraping.image_downloader import ImageDownloader


def test_image_downloader_ignores_empty_url(tmp_path):

    class FakeDownloader:
        def get(self, url):
            return b"data"

    downloader = ImageDownloader(tmp_path)

    result = downloader.download("P002", "", FakeDownloader())

    assert result is None


def test_image_downloader_does_not_download_existing_file(tmp_path):

    file = tmp_path / "P003.jpg"

    file.write_bytes(b"existing")

    class FakeDownloader:
        def get(self, url):
            raise RuntimeError("Should not download")

    downloader = ImageDownloader(tmp_path)

    result = downloader.download("P003", "http://image.jpg", FakeDownloader())

    assert result == str(file)
