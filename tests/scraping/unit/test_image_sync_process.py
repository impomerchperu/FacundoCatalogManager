from pathlib import Path
from typing import ClassVar

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

def test_image_sync_processes_products_in_input_order_with_bounded_workers(
    monkeypatch,
):
    class ProductWithCode:
        def __init__(self, code):
            self.code = code
            self.image_url = f"https://example.com/{code}.webp"

    class RecordingFuture:
        def __init__(self, result):
            self._result = result

        def result(self):
            return self._result

    class RecordingExecutor:
        max_workers = None
        submitted: ClassVar[list[str]] = []

        def __init__(self, max_workers):
            type(self).max_workers = max_workers
            type(self).submitted = []

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            return False

        def submit(self, function, product):
            type(self).submitted.append(product.code)
            return RecordingFuture(function(product))

    monkeypatch.setattr(
        "scrapers.sync.image_sync.ThreadPoolExecutor",
        RecordingExecutor,
    )

    class FakeRepository:
        def find(self, code, image_url=None):
            del code, image_url

    class FakeManager:
        def process(self, code, image_url):
            return {
                "image_path": f"data/images/products/{code}.webp",
                "image_hash": code,
            }

    products = [
        ProductWithCode("A"),
        ProductWithCode("B"),
        ProductWithCode("C"),
    ]
    sync = ImageSync(
        image_manager=FakeManager(),
        image_repository=FakeRepository(),
        max_workers=2,
    )

    result = sync.process(products)

    assert RecordingExecutor.max_workers == 2
    assert RecordingExecutor.submitted == ["A", "B", "C"]
    assert [product.code for product in result] == ["A", "B", "C"]


def test_image_sync_rejects_invalid_worker_count():
    try:
        ImageSync(max_workers=0)
    except ValueError:
        pass
    else:
        raise AssertionError("max_workers debe ser mayor que cero")


