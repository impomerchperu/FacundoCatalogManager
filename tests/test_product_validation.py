from models.product import Product


def test_product_requires_code():

    product = Product(
        code="",
        name="Producto",
        category="General",
        description="",
        price=10,
        stock=5
    )

    errors = product.validate()

    assert "El código es obligatorio" in errors



def test_product_requires_name():

    product = Product(
        code="P001",
        name="",
        category="General",
        description="",
        price=10,
        stock=5
    )

    errors = product.validate()

    assert "El nombre es obligatorio" in errors



def test_product_rejects_negative_price():

    product = Product(
        code="P001",
        name="Producto",
        category="General",
        description="",
        price=-10,
        stock=5
    )

    errors = product.validate()

    assert "El precio no puede ser negativo" in errors



def test_product_rejects_negative_stock():

    product = Product(
        code="P001",
        name="Producto",
        category="General",
        description="",
        price=10,
        stock=-5
    )

    errors = product.validate()

    assert "El stock no puede ser negativo" in errors



def test_product_normalize():

    product = Product(
        code=" P001 ",
        name="  Producto prueba ",
        category=" General ",
        description=" Descripción ",
        price=10,
        stock=5
    )


    product.normalize()


    assert product.code == "P001"
    assert product.name == "Producto prueba"
    assert product.category == "General"
    assert product.description == "Descripción"