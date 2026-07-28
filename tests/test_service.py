from database.db_manager import DBManager
from models.product import Product
from services.product_service import ProductService


def test_create_product():

    db = DBManager()

    # limpiar datos anteriores
    db.execute_query(
        "DELETE FROM products"
    )

    db.close()

    service = ProductService()

    producto = Product(
        code="TEST002",
        name="Segundo producto",
        category="General",
        description="Producto creado mediante servicio",
        price=35.90,
        stock=5,
        image_path="",
    )

    service.create_product(producto)

    productos = service.get_products()

    assert len(productos) == 1
    assert productos[0][1] == "TEST002"