from scrapers.images.safe_image_manager import SafeImageManager


class FakeDownloader:
    def download(self, code, url):
        return ""


class FakeRepository:
    def find(self, code):
        return None


manager = SafeImageManager(
    downloader=FakeDownloader(),
    repository=FakeRepository(),
)


result = manager.process("FB-1812", "http://test.com/image.webp")


print("=" * 80)
print("IMAGE ERROR HANDLING")
print("=" * 80)

print(result)


assert result["image_path"] == ""
assert result["image_hash"] == ""
assert result["image_error"] == "Download failed"


print()
print("OK")
