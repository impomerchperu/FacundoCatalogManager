from scrapers.images.safe_image_manager import SafeImageManager


class FakeDownloader:
    def download(self, code, url):
        return ""


class FakeRepository:
    def find(self, code):
        return None


def test_safe_image_manager_handles_empty_download():
    manager = SafeImageManager(
        downloader=FakeDownloader(),
        repository=FakeRepository(),
    )

    result = manager.process(
        "FB-1812",
        "http://test.com/image.webp",
    )

    assert result["image_path"] == ""
    assert result["image_hash"] == ""
    assert result["image_error"] == "Download failed"
