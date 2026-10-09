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


def test_delete_category_removes_only_category_and_keeps_products(repository):
    first = repository.create(
        Product(
            code="CAT001",
            name="Producto 1",
            category="Cocina, Mesa y Hogar",
        )
    )
    second = repository.create(
        Product(
            code="CAT002",
            name="Producto 2",
            category="Cocina, Mesa y Hogar, Artículos Antiestrés",
        )
    )

    repository.db.execute_query(
        "INSERT INTO categories (name, canonical_url) VALUES (?, ?)",
        ("Cocina, Mesa y Hogar", "https://example.test/cocina"),
    )
    category = repository.db.fetch_one(
        "SELECT id FROM categories WHERE canonical_url=?",
        ("https://example.test/cocina",),
    )
    assert category is not None
    repository.db.execute_many(
        "INSERT INTO product_categories (product_id, category_id) VALUES (?, ?)",
        [
            (first.id, category["id"]),
            (second.id, category["id"]),
        ],
    )

    anti = repository.db.fetch_one(
        "SELECT id FROM categories WHERE name=?",
        ("Artículos Antiestrés",),
    )
    if anti is None:
        repository.db.execute_query(
            "INSERT INTO categories (name, canonical_url) VALUES (?, ?)",
            ("Artículos Antiestrés", "https://example.test/antiestrés"),
        )
        anti = repository.db.fetch_one(
            "SELECT id FROM categories WHERE name=?",
            ("Artículos Antiestrés",),
        )
    assert anti is not None
    repository.db.execute_query(
        "INSERT INTO product_categories (product_id, category_id) VALUES (?, ?)",
        (second.id, anti["id"]),
    )

    affected = repository.delete_category("Cocina, Mesa y Hogar")

    assert affected == 2
    first_loaded = repository.get_by_id(first.id)
    second_loaded = repository.get_by_id(second.id)
    assert first_loaded is not None
    assert second_loaded is not None
    assert first_loaded.category == ""
    assert second_loaded.category == "Artículos Antiestrés"

    assert repository.db.fetch_one(
        "SELECT COUNT(*) AS total FROM product_categories WHERE product_id=? AND category_id=?",
        (first.id, category["id"]),
    )["total"] == 0
    assert repository.db.fetch_one(
        "SELECT COUNT(*) AS total FROM product_categories WHERE product_id=? AND category_id=?",
        (second.id, category["id"]),
    )["total"] == 0
    assert repository.db.fetch_one(
        "SELECT COUNT(*) AS total FROM product_categories WHERE product_id=? AND category_id=?",
        (second.id, anti["id"]),
    )["total"] == 1


def test_next_product_code_uses_highest_numeric_fb_code(repository):
    repository.create(Product(code="FB-0042", name="Uno"))
    repository.create(Product(code="FB-0100", name="Dos"))
    repository.create(Product(code="IKIOSK-9999", name="Otro"))

    assert repository.next_product_code() == "FB-0101"


def test_repository_persists_local_gallery_images(repository):
    product = repository.create(
        Product(
            code="FB-0102",
            name="Galería local",
            image_path="images/primary.jpg",
            gallery_images=[
                {
                    "url": "",
                    "image_path": "images/primary.jpg",
                    "position": 1,
                    "source": "manual",
                },
                {
                    "url": "",
                    "image_path": "images/alternative.jpg",
                    "position": 2,
                    "source": "manual",
                },
            ],
        )
    )

    loaded = repository.get_by_id(product.id)

    assert loaded is not None
    assert [image["image_path"] for image in loaded.gallery_images] == [
        "images/primary.jpg",
        "images/alternative.jpg",
    ]

def test_service_syncs_product_category_relationships(repository):
    from services.product_service import ProductService

    service = ProductService(repository)
    product = service.create_product(
        Product(
            code="REL001",
            name="Relaciones",
            category="Artículos de Playa",
        )
    )

    category = repository.db.fetch_one(
        "SELECT id FROM categories WHERE name=?",
        ("Artículos de Playa",),
    )
    assert category is not None
    linked = repository.db.fetch_one(
        "SELECT COUNT(*) AS total FROM product_categories WHERE product_id=? AND category_id=?",
        (product.id, category["id"]),
    )
    assert linked["total"] == 1

    service.update_product(
        Product(
            code=product.code,
            name=product.name,
            category="Artículos de Playa y Verano, Artículos Antiestrés",
            product_id=product.id,
        )
    )

    updated = repository.get_by_id(product.id)
    assert updated is not None
    assert updated.category == "Artículos de Playa y Verano, Artículos Antiestrés"

    old_link = repository.db.fetch_one(
        "SELECT COUNT(*) AS total FROM product_categories pc "
        "JOIN categories c ON c.id=pc.category_id "
        "WHERE pc.product_id=? AND c.name=?",
        (product.id, "Artículos de Playa"),
    )
    assert old_link["total"] == 0

    new_link = repository.db.fetch_one(
        "SELECT COUNT(*) AS total FROM product_categories pc "
        "JOIN categories c ON c.id=pc.category_id "
        "WHERE pc.product_id=? AND c.name=?",
        (product.id, "Artículos de Playa y Verano"),
    )
    anti_link = repository.db.fetch_one(
        "SELECT COUNT(*) AS total FROM product_categories pc "
        "JOIN categories c ON c.id=pc.category_id "
        "WHERE pc.product_id=? AND c.name=?",
        (product.id, "Artículos Antiestrés"),
    )
    assert new_link["total"] == 1
    assert anti_link["total"] == 1


