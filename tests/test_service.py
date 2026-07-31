from database.db_manager import DBManager
from models.product import Product
from services.product_service import ProductService


def clean_database():

    db = DBManager()

    db.execute_query("DELETE FROM products")

    db.close()


def test_create_product():

    clean_database()

    service = ProductService()

    product = Product(
        code="TEST002",
        name="Segundo producto",
        category="General",
        description="Producto creado mediante servicio",
        price=35.90,
        stock=5,
        image_path="",
    )

    created = service.create_product(product)

    products = service.get_products()

    assert len(products) == 1

    assert created.code == "TEST002"

    assert products[0].name == "Segundo producto"


def test_create_invalid_product():

    clean_database()

    service = ProductService()

    product = Product(
        code="",
        name="",
        category="General",
        description="Producto inválido",
        price=-10,
        stock=-5,
        image_path="",
    )

    try:
        service.create_product(product)

        assert False, "Debió rechazar producto inválido"

    except ValueError as error:
        assert len(error.args[0]) > 0


def test_update_product():

    clean_database()

    service = ProductService()

    product = Product(
        code="UP001",
        name="Producto original",
        category="Test",
        description="Antes",
        price=10,
        stock=1,
        image_path="",
    )

    service.create_product(product)

    product.name = "Producto actualizado"
    product.price = 99

    service.update_product(product)

    products = service.get_products()

    assert products[0].name == "Producto actualizado"

    assert products[0].price == 99


def test_delete_product():

    clean_database()

    service = ProductService()

    product = Product(
        code="DEL001",
        name="Eliminar",
        category="Test",
        description="Eliminar producto",
        price=20,
        stock=2,
        image_path="",
    )

    service.create_product(product)

    service.delete_product(product.id)

    products = service.get_products()

    assert len(products) == 0
