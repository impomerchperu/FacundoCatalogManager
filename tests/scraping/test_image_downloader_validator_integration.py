from utils.scraping.image_downloader import ImageDownloader


def test_image_downloader_rejects_invalid_image(tmp_path):

    class FakeDownloader:

        def get(self, url):
            return b"invalid-data"


    downloader = ImageDownloader(
        tmp_path
    )


    result = downloader.download(
        "P001",
        "http://image.jpg",
        FakeDownloader()
    )


    assert result is None