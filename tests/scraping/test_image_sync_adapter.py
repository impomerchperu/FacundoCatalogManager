from services.scraping.image_sync_adapter import (
    ImageSyncAdapter,
)


def test_image_sync_adapter_processes_products():

    class FakeImageSync:

        def __init__(self):
            self.called = False

        def process(self, products):

            self.called = True

            return products


    image_sync = FakeImageSync()

    adapter = ImageSyncAdapter(
        image_sync=image_sync,
    )

    products = [
        {
            "code": "P001",
            "image_url": "image.jpg",
        }
    ]

    result = adapter.sync_products(
        products,
    )

    assert image_sync.called is True

    assert result == products
