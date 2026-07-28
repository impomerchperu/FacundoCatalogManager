from database.db_manager import DBManager
from models.product import Product
from repositories.product_repository import ProductRepository


def clean_database():
    db = DBManager()
    db.execute_query("DELETE FROM products")
    db.close()


def test_create_and_get_all():

    clean_database()

    repository = ProductRepository()

    product = Product(
        code="REP001",
        name="Producto Repository",
        category="Test",
        description="Prueba de repositorio",
        price=50.0,
        stock=20,
        image_path="",
    )

    repository.create(product)

    products = repository.get_all()

    assert len(products) == 1
    assert products[0][1] == "REP001"


def test_search_product():

    clean_database()

    repository = ProductRepository()

    product = Product(
        code="REP002",
        name="Producto Busqueda",
        category="Electronica",
        description="Prueba search",
        price=100.0,
        stock=5,
        image_path="",
    )

    repository.create(product)

    results = repository.search("Busqueda")

    assert len(results) == 1
    assert results[0][1] == "REP002"


def test_delete_product():

    clean_database()

    repository = ProductRepository()

    product = Product(
        code="REP003",
        name="Producto Eliminar",
        category="Test",
        description="Prueba delete",
        price=20.0,
        stock=2,
        image_path="",
    )

    repository.create(product)

    products = repository.get_all()

    product_id = products[0][0]

    repository.delete(product_id)

    products_after = repository.get_all()

    assert len(products_after) == 0


def test_update_product():

    clean_database()

    repository = ProductRepository()

    product = Product(
        code="REP004",
        name="Producto Original",
        category="Test",
        description="Antes",
        price=10,
        stock=1,
        image_path="",
    )

    repository.create(product)

    products = repository.get_all()

    product_id = products[0][0]

    product.id = product_id
    product.name = "Producto Actualizado"
    product.price = 99

    repository.update(product)

    updated = repository.get_by_id(product_id)

    assert updated[2] == "Producto Actualizado"
    assert updated[5] == 99