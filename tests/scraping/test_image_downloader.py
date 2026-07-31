from utils.scraping.image_downloader import ImageDownloader


def test_image_downloader_saves_image(tmp_path):

    class FakeDownloader:
        def get(self, url):

            return b"\xff\xd8fake-image-data"

    downloader = ImageDownloader(tmp_path)

    result = downloader.download("P001", "http://image.jpg", FakeDownloader())

    file = tmp_path / "P001.jpg"

    assert result == str(file)

    assert file.exists()

    assert file.read_bytes() == b"\xff\xd8fake-image-data"
