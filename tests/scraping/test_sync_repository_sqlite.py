from database.db_manager import DBManager
from repositories.scraping.sync_repository import SyncRepository


class Product:

    code = "SYNC001"
    name = "Producto Sync"
    category = "Test"
    price = 25
    stock = 5
    image_path = "img.jpg"
    image_url = "url.jpg"



def test_sync_repository_save_and_get():

    db = DBManager(":memory:")

    db.initialize_database()


    repository = SyncRepository(
        db
    )


    product = Product()


    repository.save(
        product
    )


    result = repository.get(
        "SYNC001"
    )


    assert result["code"] == "SYNC001"
    assert result["name"] == "Producto Sync"