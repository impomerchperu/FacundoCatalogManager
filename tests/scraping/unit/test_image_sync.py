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
    def find(self, code, image_url=None):
        del code, image_url
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


class ExistingRepository:
    def find(self, code, image_url=None):
        del code
        if image_url and image_url.endswith(".webp"):
            return {
                "image_path": "data/images/products/FB-1812.webp",
                "image_hash": "webp-hash",
            }
        return {
            "image_path": "data/images/products/FB-1812.jpg",
            "image_hash": "jpg-hash",
        }


def test_image_sync_uses_repository_image_matching_current_url_extension():
    class ProductWithCurrentWebp:
        code = "FB-1812"
        image_url = "https://site.com/FB-1812.webp"

    sync = ImageSync(
        image_manager=FakeManager(),
        image_repository=ExistingRepository(),
    )

    result = sync.synchronize(ProductWithCurrentWebp())

    assert Path(result["image_path"]) == Path(
        "data/images/products/FB-1812.webp"
    )
    assert result["image_hash"] == "webp-hash"
