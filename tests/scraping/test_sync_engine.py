from models.scraping.scraped_product import ScrapedProduct
from scrapers.sync.sync_engine import SyncEngine
from scrapers.sync.sync_result import SyncResult


class FakeRepository:

    def __init__(self, products=None):
        self.products = products or []
        self.saved = []


    def load(self):
        return self.products


    def save(self, products):
        self.saved = products



class FakeImageSync:

    def sync_product(
        self,
        product,
        old_product=None,
    ):

        product.image_path = "image.jpg"

        product.image_hash = "hash123"

        return product



def create_product(
    code="P001",
    stock=10,
):

    return ScrapedProduct(
        source="test",
        url=f"https://test/{code}",
        code=code,
        name="Producto",
        category="Test",
        stock=stock,
        price_sample=10,
        image_url="image.jpg",
    )



def test_sync_engine_detects_new_product():

    repository = FakeRepository()

    engine = SyncEngine(
        storage=repository,
    )


    result = engine.synchronize(
        [
            create_product()
        ]
    )


    assert isinstance(
        result,
        SyncResult,
    )

    assert result.new_count == 1



def test_sync_engine_detects_unchanged_product():

    old = create_product()

    repository = FakeRepository(
        [
            old
        ]
    )


    engine = SyncEngine(
        storage=repository,
    )


    result = engine.synchronize(
        [
            create_product()
        ]
    )


    assert result.unchanged_count == 1



def test_sync_engine_processes_image_for_new_product():

    repository = FakeRepository()

    engine = SyncEngine(
        storage=repository,
        image_sync=FakeImageSync(),
    )


    result = engine.synchronize(
        [
            create_product()
        ]
    )


    assert result.images_processed == 1

    assert repository.saved[0].image_path == "image.jpg"



def test_sync_engine_detects_updated_product():

    old = create_product(
        stock=10,
    )

    repository = FakeRepository(
        [
            old
        ]
    )


    engine = SyncEngine(
        storage=repository,
        image_sync=FakeImageSync(),
    )


    new = create_product(
        stock=20,
    )


    result = engine.synchronize(
        [
            new
        ]
    )


    assert result.updated_count == 1

    assert repository.saved[0].stock == 20
