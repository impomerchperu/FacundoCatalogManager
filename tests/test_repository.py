import json

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

    created = repository.create(product)

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

    repository.create(product)

    results = repository.search("Busqueda")

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

    repository.create(product)

    repository.delete(product.id)

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

    repository.create(product)

    product.name = "Producto Actualizado"
    product.price = 99

    repository.update(product)

    updated = repository.get_by_id(product.id)

    assert updated is not None
    assert updated.name == "Producto Actualizado"
    assert updated.price == 99


def test_repository_ignores_malformed_color_stock(repository):
    malformed_color = (
        'var acss = {"color_mode":"light"}; '
        "//# sourceURL=color-scheme-switcher-frontend-js-extra"
    )
    product = Product(
        code="REP005",
        name="Producto con stock contaminado",
        stock=370,
        color_stock={
            malformed_color: 370,
            "Rojo": 12,
        },
    )
    repository.create(product)

    row = repository.db.fetch_one(
        "SELECT color_stock FROM products WHERE code=?",
        ("REP005",),
    )
    repository.db.execute_query(
        "UPDATE products SET color_stock=? WHERE code=?",
        (row["color_stock"], "REP005"),
    )

    loaded = repository.get_by_code("REP005")

    assert loaded is not None
    assert loaded.color_stock == {"Rojo": 12}


def test_repository_filters_malformed_json_color_stock(repository):
    malformed_color = (
        'var acss = {"color_mode":"light"}; '
        "//# sourceURL=color-scheme-switcher-frontend-js-extra"
    )
    repository.db.execute_query(
        """
        INSERT INTO products (
            code, name, category, description, price,
            price_sample, price_hundred, price_thousand, stock,
            color_stock, image_url, image_path, image_hash, content_hash
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "REP006",
            "Producto JSON contaminado",
            "",
            "",
            0,
            0,
            0,
            0,
            124904,
            json.dumps({malformed_color: 124904}),
            "",
            "",
            "",
            "",
        ),
    )

    loaded = repository.get_by_code("REP006")

    assert loaded is not None
    assert loaded.color_stock == {}
    assert loaded.stock == 124904
