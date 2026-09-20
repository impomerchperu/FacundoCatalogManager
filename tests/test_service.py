import pytest

from database.db_manager import DBManager
from models.product import Product
from repositories.product_repository import ProductRepository
from services.product_service import ProductService


@pytest.fixture
def service():
    db = DBManager(":memory:")
    yield ProductService(ProductRepository(db))
    db.close()


def test_create_product(service):
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


def test_create_invalid_product(service):
    product = Product(
        code="",
        name="",
        category="General",
        description="Producto inválido",
        price=-10,
        stock=-5,
        image_path="",
    )

    with pytest.raises(ValueError) as error:
        service.create_product(product)

    assert len(error.value.args[0]) > 0


def test_update_product(service):
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


def test_delete_product(service):
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
