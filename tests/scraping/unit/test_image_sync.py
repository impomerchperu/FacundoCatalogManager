from pathlib import Path

from scrapers.sync.image_sync import ImageSync


class FakeManager:
    def process(
        self,
        code,
        url,
    ):
        return {
            "image_path": f"data/images/products/{code}.webp",
            "image_hash": "abc123",
        }


class EmptyRepository:
    def find(self, code):
        return None


class Product:
    code = "FB-1812"
    image_url = "https://site.com/FB-1812.webp"


def test_image_sync_synchronizes_product_image():
    sync = ImageSync(
        image_manager=FakeManager(),
        image_repository=EmptyRepository(),
    )

    result = sync.synchronize(Product())

    assert Path(result["image_path"]) == Path(
        "data/images/products/FB-1812.webp"
    )
    assert result["image_hash"] == "abc123"
