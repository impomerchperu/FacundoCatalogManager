from database.db_manager import DBManager
from models.scraping.scraped_product import ScrapedProduct
from repositories.scraping.sync_repository import SyncRepository
from scrapers.sync.sync_engine import SyncEngine


def create_product(
    code="SQL001",
    stock=10,
):

    return ScrapedProduct(
        source="test",
        url=f"https://test/{code}",
        code=code,
        name="Producto SQLite",
        category="Test",
        description="Producto prueba",
        stock=stock,
        price_sample=15,
        image_url="image.jpg",
    )


def test_sync_engine_with_sqlite_repository():

    db = DBManager(":memory:")

    repository = SyncRepository(db)


    engine = SyncEngine(
        storage=repository,
    )


    first = create_product(
        stock=10,
    )


    first_result = engine.synchronize(
        [
            first
        ]
    )


    assert first_result.new_count == 1


    stored = repository.get(
        "SQL001"
    )


    assert stored is not None
    assert stored["code"] == "SQL001"
    assert stored["stock"] == 10



    second = create_product(
        stock=25,
    )


    second_result = engine.synchronize(
        [
            second
        ]
    )


    assert second_result.updated_count == 1


    updated = repository.get(
        "SQL001"
    )


    assert updated is not None
    assert updated["stock"] == 25


    db.close()
