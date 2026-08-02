from scrapers.images.image_manager import ImageManager


class FakeDownloader:

    def download(
        self,
        code,
        url
    ):

        return ""



manager = ImageManager(
    downloader=FakeDownloader()
)


result = manager.process(
    "FB-1812",
    "http://test.com/image.webp"
)


print("="*80)
print("IMAGE ERROR HANDLING")
print("="*80)

print(result)


assert result["image_path"] == ""

assert result["image_hash"] == ""

assert result["image_error"] == "Download failed"


print()
print("OK")