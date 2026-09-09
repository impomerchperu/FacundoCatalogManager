import requests

from scrapers.images.safe_image_manager import SafeImageManager


class FakeRepository:
    def find(self, code):
        return None


def test_safe_image_manager_contains_read_timeout():
    class FailingDownloader:
        def download(self, code, url):
            raise requests.exceptions.ReadTimeout("timed out")

    manager = SafeImageManager(
        downloader=FailingDownloader(),
        repository=FakeRepository(),
    )

    result = manager.process(
        "FB-1813",
        "http://test.com/image.webp",
    )

    assert result == {
        "image_path": "",
        "image_hash": "",
        "image_error": "timed out",
    }
