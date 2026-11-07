from database.db_manager import DBManager
from models.product import Product


def test_product_repository_round_trips_gallery_images(repository):
    product = Product(
        code="FB-4010",
        name="Gota Antiestrés",
        image_url="https://site.test/one.webp",
        image_path="data/images/products/FB-4010.webp",
        gallery_images=[
            {
                "url": "https://site.test/one.webp",
                "image_path": "data/images/gallery/FB-4010/FB-4010-01.webp",
                "image_hash": "hash-one",
                "position": 1,
                "source": "woocommerce-gallery",
            },
            {
                "url": "https://site.test/two.webp",
                "image_path": "data/images/gallery/FB-4010/FB-4010-02.webp",
                "image_hash": "hash-two",
                "position": 2,
                "source": "woocommerce-gallery",
            },
        ],
    )

    repository.create(product)
    loaded = repository.get_by_code("FB-4010")

    assert loaded is not None
    assert loaded.gallery_images == product.gallery_images


def test_product_repository_round_trips_detail_html_without_changing_text(repository):
    source_html = (
        '<p style="text-align: center"><strong>Marca:</strong> Bright Office</p>'
        '<p><strong>Modelo:</strong> 230</p>'
    )
    product = Product(
        code="FB-1504",
        name="Enmicadora Metálica A4",
        description="Marca: Bright Office\nModelo: 230",
        description_html=source_html,
    )

    repository.create(product)
    loaded = repository.get_by_code("FB-1504")

    assert loaded is not None
    assert loaded.description == product.description
    assert loaded.description_html == source_html


def test_schema_v7_adds_detail_markup_column_without_changing_legacy_text(tmp_path):
    database_path = tmp_path / "legacy-catalog.db"
    database = DBManager(str(database_path))
    database.execute_query(
        "ALTER TABLE products DROP COLUMN description_html"
    )
    database.execute_query(
        "DELETE FROM schema_migrations WHERE version=7"
    )
    legacy_text = "Marca: Bright Office\nModelo: 230"
    database.execute_query(
        "INSERT INTO products (code, name, description) VALUES (?, ?, ?)",
        ("FB-1504", "Enmicadora Metálica A4", legacy_text),
    )
    database.close()

    migrated = DBManager(str(database_path))
    try:
        columns = {
            row["name"]
            for row in migrated.fetch_all("PRAGMA table_info(products)")
        }
        assert "description_html" in columns
        product = ProductRepository(migrated).get_by_code("FB-1504")
        assert product is not None
        assert product.description == legacy_text
        assert product.description_html == ""
        assert migrated.fetch_one(
            "SELECT version FROM schema_migrations WHERE version=7"
        ) is not None
    finally:
        migrated.close()
