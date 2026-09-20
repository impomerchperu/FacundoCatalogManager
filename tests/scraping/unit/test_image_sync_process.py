from pathlib import Path

from models.scraping.scraped_product import ScrapedProduct
from scrapers.sync.image_sync import ImageSync


class FakeImageManager:
    def process(
        self,
        code,
        image_url,
    ):
        return {
            "image_path": "data/images/products/FB-1812.webp",
            "image_hash": "hash123",
        }


class EmptyRepository:
    def find(self, code, image_url=None):
        del code, image_url


def test_image_sync_processes_products():
    sync = ImageSync(
        image_manager=FakeImageManager(),
        image_repository=EmptyRepository(),
    )

    product = ScrapedProduct(
        code="FB-1812",
        image_url="http://test.com/image.webp",
    )

    result = sync.process([product])

    assert len(result) == 1
    assert Path(result[0].image_path) == Path(
        "data/images/products/FB-1812.webp"
    )
    assert result[0].image_hash == "hash123"
