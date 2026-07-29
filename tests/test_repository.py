from models.product import Product



def test_create_and_get_all(repository):

    product = Product(
        code="REP001",
        name="Producto Repository",
        category="Test",
        description="Prueba de repositorio",
        price=50.0,
        stock=20,
        image_path="",
    )


    created = repository.create(
        product
    )


    products = repository.get_all()


    assert created.id is not None

    assert len(products) == 1

    assert products[0].code == "REP001"



def test_search_product(repository):

    product = Product(
        code="REP002",
        name="Producto Busqueda",
        category="Electronica",
        description="Prueba search",
        price=100.0,
        stock=5,
        image_path="",
    )


    repository.create(
        product
    )


    results = repository.search(
        "Busqueda"
    )


    assert len(results) == 1

    assert results[0].code == "REP002"



def test_delete_product(repository):

    product = Product(
        code="REP003",
        name="Producto Eliminar",
        category="Test",
        description="Prueba delete",
        price=20,
        stock=2,
        image_path="",
    )


    repository.create(
        product
    )


    repository.delete(
        product.id
    )


    products = repository.get_all()


    assert len(products) == 0



def test_update_product(repository):

    product = Product(
        code="REP004",
        name="Producto Original",
        category="Test",
        description="Antes",
        price=10,
        stock=1,
        image_path="",
    )


    repository.create(
        product
    )


    product.name = "Producto Actualizado"

    product.price = 99


    repository.update(
        product
    )


    updated = repository.get_by_id(
        product.id
    )


    assert updated is not None

    assert updated.name == "Producto Actualizado"

    assert updated.price == 99