from utils.scraping.image_download_manager import ImageDownloadManager


def test_image_download_manager_downloads_multiple_images():

    class FakeDownloader:

        def get(self, url):
            return b"\xff\xd8fake-image"


    class FakeImageDownloader:

        def __init__(self):

            self.calls = []


        def download(
            self,
            code,
            url,
            downloader
        ):

            self.calls.append(
                (code, url)
            )

            return f"{code}.jpg"


    image_downloader = FakeImageDownloader()


    manager = ImageDownloadManager(
        image_downloader,
        max_workers=3
    )


    products = [
        {
            "code": "P001",
            "image": "http://image1.jpg"
        },
        {
            "code": "P002",
            "image": "http://image2.jpg"
        }
    ]


    result = manager.download_all(
        products,
        FakeDownloader()
    )


    assert result == [
        "P001.jpg",
        "P002.jpg"
    ]


    assert len(
        image_downloader.calls
    ) == 2