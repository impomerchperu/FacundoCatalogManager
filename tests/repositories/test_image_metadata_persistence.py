from database.db_manager import DBManager
from models.product import Product
from repositories.product_repository import ProductRepository


def test_primary_image_revalidation_metadata_survives_database_roundtrip(tmp_path):
    db_path = tmp_path / "catalog.db"
    db = DBManager(str(db_path))
    repository = ProductRepository(db)
    product = Product(
        code="TEST-ETAG",
        name="Producto de prueba",
        image_url="https://example.test/product.webp",
        image_path="data/images/products/TEST-ETAG/TEST-ETAG-01.webp",
        image_hash="sha256-value",
        image_etag='"revision-1"',
        image_last_modified="Sun, 18 Oct 2026 00:00:00 GMT",
        image_checked_at="2026-10-18T00:00:00+00:00",
    )
    repository.create(product)
    db.commit()
    db.close()

    reopened_db = DBManager(str(db_path))
    reopened = ProductRepository(reopened_db).get_by_code("TEST-ETAG")

    assert reopened is not None
    assert reopened.image_hash == "sha256-value"
    assert reopened.image_etag == '"revision-1"'
    assert reopened.image_last_modified == "Sun, 18 Oct 2026 00:00:00 GMT"
    assert reopened.image_checked_at == "2026-10-18T00:00:00+00:00"

    reopened.image_etag = '"revision-2"'
    reopened.image_checked_at = "2026-10-18T01:00:00+00:00"
    ProductRepository(reopened_db).update(reopened)
    reopened_db.commit()

    updated = ProductRepository(reopened_db).get_by_code("TEST-ETAG")
    assert updated is not None
    assert updated.image_etag == '"revision-2"'
    assert updated.image_checked_at == "2026-10-18T01:00:00+00:00"
    reopened_db.close()
