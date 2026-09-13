from database.db_manager import DBManager
from repositories.scraping.normalized_scraping_repository import (
    NormalizedScrapingRepository,
)


def test_normalized_repository_persists_canonical_category_name():
    db = DBManager(":memory:")
    repository = NormalizedScrapingRepository(db)

    repository.upsert_category(
        "cocina mesa y hogar",
        "https://example.test/cocina-mesa-hogar/",
        expected_count=12,
    )

    row = db.fetch_one(
        "SELECT name, canonical_url, expected_count FROM categories"
    )

    assert row["name"] == "Cocina, Mesa y Hogar"
    assert row["canonical_url"] == "https://example.test/cocina-mesa-hogar"
    assert row["expected_count"] == 12

    db.close()
