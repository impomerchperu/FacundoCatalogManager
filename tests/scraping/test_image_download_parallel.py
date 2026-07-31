from services.scraping.image_download_manager import ImageDownloadManager


def test_image_download_manager_parallel_download():

    class FakeDownloader:
        def get(self, url):
            return b"image"

    class FakeImageDownloader:
        def download(self, code, url, downloader):

            return f"{code}.jpg"

    class FakeValidator:
        def is_valid(self, path):

            return True

    manager = ImageDownloadManager(
        FakeImageDownloader(), FakeValidator(), max_workers=2
    )

    products = [
        {"code": "P001", "image": "img1.jpg"},
        {"code": "P002", "image": "img2.jpg"},
    ]

    result = manager.download_all(products, FakeDownloader())

    assert len(result) == 2

    assert result[0]["image_path"] == "P001.jpg"

    assert result[1]["image_path"] == "P002.jpg"
