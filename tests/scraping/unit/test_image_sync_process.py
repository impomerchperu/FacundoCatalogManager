from models.scraping.scraped_product import ScrapedProduct
from scrapers.sync.image_sync import ImageSync


class FakeImageManager:
    def process(
        self,
        code,
        image_url,
    ):

        return {"image_path": "data/images/test.webp", "image_hash": "hash123"}


sync = ImageSync(image_manager=FakeImageManager())


product = ScrapedProduct(code="FB-1812", image_url="http://test.com/image.webp")


result = sync.process([product])


print("=" * 80)
print("IMAGE SYNC ENGINE")
print("=" * 80)


print(result[0])


assert result[0].image_path == ("data/images/test.webp")

assert result[0].image_hash == ("hash123")


print()
print("OK")
