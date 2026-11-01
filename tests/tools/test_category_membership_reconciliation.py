from types import SimpleNamespace

import pytest

from database.db_manager import DBManager
from models.product import Product
from models.scraping.category import Category
from repositories.product_repository import ProductRepository
from repositories.scraping.normalized_scraping_repository import (
    NormalizedScrapingRepository,
)
from services.scraping.product_hash_service import ProductHashService
from tools.category_membership_reconciliation import (
    apply_live_category_membership_reconciliation,
    audit_live_category_memberships,
    validate_membership_audit_approval,
)


def _seed_product(
    repository: ProductRepository,
    code: str,
    category: str,
) -> Product:
    product = repository.save(
        Product(
            code=code,
            name=f"Producto {code}",
            category=category,
            description="Material: ABS.",
        )
    )
    assert product.product_id is not None
    repository.sync_product_categories(product.product_id, category)
    return product


class StaticCollectionScraper:
    def __init__(self, products_by_category):
        self.products_by_category = products_by_category

    def collect_category(self, category):
        return self.products_by_category[category.name]


def _source_card(code: str):
    return (
        None,
        f"https://stock.importacionesfacundo.com/categoria/{code.lower()}/",
        SimpleNamespace(code=code, name=f"Producto {code}"),
    )


def _categories(desktop_count: int, case_count: int):
    return [
        Category(
            name="Artículos de Escritorio",
            url="https://stock.importacionesfacundo.com/categoria/escritorio/",
            expected_count=desktop_count,
        ),
        Category(
            name="Estuches",
            url="https://stock.importacionesfacundo.com/categoria/estuches/",
            expected_count=case_count,
        ),
    ]


def test_membership_audit_plans_removal_from_stale_database_category():
    db = DBManager(":memory:")
    repository = ProductRepository(db)
    _seed_product(
        repository,
        "FB-1600",
        "Artículos de Escritorio, Estuches",
    )
    _seed_product(repository, "FB-1601", "Artículos de Escritorio")

    collection = StaticCollectionScraper(
        {
            "Artículos de Escritorio": [_source_card("FB-1601")],
            "Estuches": [_source_card("FB-1600")],
        }
    )

    try:
        report, raw_by_category = audit_live_category_memberships(
            db,
            repository,
            _categories(1, 1),
            collection_scraper=collection,
        )

        assert report["coverage_verified"] is True
        assert report["category_occurrences"] == 2
        assert set(raw_by_category) == {
            "articulos escritorio",
            "estuches",
        }
        assert report["products_with_membership_changes"] == 1
        item = report["items"][0]
        assert item["code"] == "FB-1600"
        assert item["old_categories_text"] == [
            "Artículos de Escritorio",
            "Estuches",
        ]
        assert item["source_categories"] == ["Estuches"]
        assert item["added_categories"] == []
        assert item["removed_categories"] == ["Artículos de Escritorio"]
        assert item["stale_from_category_text"] == ["Artículos de Escritorio"]
        assert item["stale_from_category_relation"] == [
            "Artículos de Escritorio"
        ]
        database_multi = report["database_multi_category_products"]
        assert len(database_multi) == 1
        assert database_multi[0]["code"] == "FB-1600"
        assert database_multi[0]["database_categories"] == [
            "Artículos de Escritorio",
            "Estuches",
        ]
        assert database_multi[0]["source_categories"] == ["Estuches"]
    finally:
        db.close()


def test_membership_audit_detects_new_multi_category_membership():
    db = DBManager(":memory:")
    repository = ProductRepository(db)
    _seed_product(repository, "FB-1700", "Artículos de Escritorio")

    collection = StaticCollectionScraper(
        {
            "Artículos de Escritorio": [_source_card("FB-1700")],
            "Estuches": [_source_card("FB-1700")],
        }
    )

    try:
        report, _ = audit_live_category_memberships(
            db,
            repository,
            _categories(1, 1),
            collection_scraper=collection,
        )

        assert report["coverage_verified"] is True
        assert report["products_with_membership_changes"] == 1
        assert report["memberships_to_add"] == 1
        item = report["items"][0]
        assert item["code"] == "FB-1700"
        assert item["source_categories"] == [
            "Artículos de Escritorio",
            "Estuches",
        ]
        assert item["added_categories"] == ["Estuches"]
        assert item["missing_from_category_text"] == ["Estuches"]
        assert item["missing_from_category_relation"] == ["Estuches"]
        multi_category = report["live_multi_category_products"]
        assert len(multi_category) == 1
        assert multi_category[0]["categories"] == [
            "Artículos de Escritorio",
            "Estuches",
        ]
    finally:
        db.close()


def test_membership_apply_updates_text_and_normalized_relationships():
    db = DBManager(":memory:")
    repository = ProductRepository(db)
    _seed_product(
        repository,
        "FB-1600",
        "Artículos de Escritorio, Estuches",
    )
    _seed_product(repository, "FB-1601", "Artículos de Escritorio")

    collection = StaticCollectionScraper(
        {
            "Artículos de Escritorio": [_source_card("FB-1601")],
            "Estuches": [_source_card("FB-1600")],
        }
    )

    try:
        report, _ = audit_live_category_memberships(
            db,
            repository,
            _categories(1, 1),
            collection_scraper=collection,
        )
        result = apply_live_category_membership_reconciliation(
            db,
            repository,
            report,
            _categories(1, 1),
        )

        product = repository.get_by_code("FB-1600")
        assert product is not None
        assert product.category == "Estuches"
        assert product.content_hash == ProductHashService().generate(product)

        relations = db.fetch_all(
            """
            SELECT c.name
            FROM product_categories AS pc
            JOIN categories AS c ON c.id = pc.category_id
            WHERE pc.product_id=?
            ORDER BY c.name
            """,
            (product.product_id,),
        )
        assert [row["name"] for row in relations] == ["Estuches"]
        assert result == {
            "updated_products": 1,
            "memberships_added": 0,
            "memberships_removed": 1,
        }
        assert report["applied"] is True
        assert report["items"][0]["status"] == "updated"
    finally:
        db.close()


def test_incomplete_live_category_coverage_blocks_membership_apply():
    db = DBManager(":memory:")
    repository = ProductRepository(db)
    _seed_product(
        repository,
        "FB-1600",
        "Artículos de Escritorio, Estuches",
    )
    categories = _categories(2, 1)
    collection = StaticCollectionScraper(
        {
            "Artículos de Escritorio": [_source_card("FB-1600")],
            "Estuches": [_source_card("FB-1600")],
        }
    )

    try:
        report, _ = audit_live_category_memberships(
            db,
            repository,
            categories,
            collection_scraper=collection,
        )

        assert report["coverage_verified"] is False
        assert any("publica 2 productos" in issue for issue in report["coverage_issues"])
        assert report["items"] == []
        with pytest.raises(ValueError, match="cobertura live completa"):
            apply_live_category_membership_reconciliation(
                db,
                repository,
                report,
                categories,
            )

        product = repository.get_by_code("FB-1600")
        assert product is not None
        assert product.category == "Artículos de Escritorio, Estuches"
    finally:
        db.close()


def test_database_product_absent_from_every_live_category_loses_all_memberships():
    db = DBManager(":memory:")
    repository = ProductRepository(db)
    _seed_product(repository, "FB-1600", "Estuches")
    _seed_product(repository, "FB-1601", "Artículos de Escritorio")

    collection = StaticCollectionScraper(
        {
            "Artículos de Escritorio": [_source_card("FB-1601")],
            "Estuches": [_source_card("FB-9999")],
        }
    )

    try:
        report, _ = audit_live_category_memberships(
            db,
            repository,
            _categories(1, 1),
            collection_scraper=collection,
        )

        assert report["coverage_verified"] is True
        assert report["products_without_live_category_membership"] == [
            {
                "code": "FB-1600",
                "current_categories": ["Estuches"],
            }
        ]
        item = next(
            item for item in report["items"] if item["code"] == "FB-1600"
        )
        assert item["source_categories"] == []
        assert item["removed_categories"] == ["Estuches"]

        result = apply_live_category_membership_reconciliation(
            db,
            repository,
            report,
            _categories(1, 1),
        )

        product = repository.get_by_code("FB-1600")
        assert product is not None
        assert product.category == ""
        assert result["memberships_removed"] == 1
        relations = db.fetch_all(
            "SELECT category_id FROM product_categories WHERE product_id=?",
            (product.product_id,),
        )
        assert relations == []
    finally:
        db.close()

def test_membership_audit_removes_duplicate_logical_category_relationships():
    db = DBManager(":memory:")
    repository = ProductRepository(db)
    product = repository.save(
        Product(
            code="FB-1602",
            name="Producto Estuches",
            category="Estuches",
        )
    )
    assert product.product_id is not None

    normalized_repository = NormalizedScrapingRepository(db)
    official_id = normalized_repository.upsert_category(
        "Estuches",
        "https://stock.importacionesfacundo.com/categoria/estuches/",
        1,
    )
    duplicate_id = normalized_repository.upsert_category(
        "Estuches",
        "https://stock.importacionesfacundo.com/categoria/estuches-antiguo/",
        1,
    )
    for category_id in (official_id, duplicate_id):
        db.execute_query(
            """
            INSERT INTO product_categories
                (product_id, category_id, first_seen_at, last_seen_at)
            VALUES (?, ?, ?, ?)
            """,
            (product.product_id, category_id, "seed", "seed"),
        )

    live_category = Category(
        name="Estuches",
        url="https://stock.importacionesfacundo.com/categoria/estuches/",
        expected_count=1,
    )
    collection = StaticCollectionScraper(
        {"Estuches": [_source_card("FB-1602")]}
    )

    try:
        report, _ = audit_live_category_memberships(
            db,
            repository,
            [live_category],
            collection_scraper=collection,
        )

        assert report["coverage_verified"] is True
        assert report["products_with_membership_changes"] == 1
        item = report["items"][0]
        assert item["code"] == "FB-1602"
        assert item["has_duplicate_or_unmapped_relations"] is True
        assert len(item["old_category_relation_ids"]) == 2

        apply_live_category_membership_reconciliation(
            db,
            repository,
            report,
            [live_category],
        )

        relation_rows = db.fetch_all(
            """
            SELECT c.canonical_url
            FROM product_categories AS pc
            JOIN categories AS c ON c.id = pc.category_id
            WHERE pc.product_id=?
            """,
            (product.product_id,),
        )
        assert [row["canonical_url"] for row in relation_rows] == [
            "https://stock.importacionesfacundo.com/categoria/estuches"
        ]
    finally:
        db.close()

def test_membership_apply_approval_requires_exact_preview_match():
    approved = {
        "coverage_verified": True,
        "coverage_issues": [],
        "fetch_errors": 0,
        "categories_scanned": 24,
        "category_scans": [{"category": "Estuches", "expected": 1, "actual": 1}],
        "category_occurrences": 1,
        "catalog_products": 1,
        "products_with_source_membership": 1,
        "products_without_live_category_membership": [],
        "live_products_not_in_database": [],
        "live_multi_category_products": [],
        "database_multi_category_products": [],
        "products_with_membership_changes": 1,
        "memberships_to_add": 0,
        "memberships_to_remove": 1,
        "unchanged_products": 0,
        "items": [
            {
                "code": "FB-1600",
                "source_categories": ["Estuches"],
                "removed_categories": ["Artículos de Escritorio"],
            }
        ],
    }

    validate_membership_audit_approval(dict(approved), dict(approved))

    changed = dict(approved)
    changed["items"] = [
        {
            "code": "FB-1600",
            "source_categories": ["Estuches", "Artículos de Escritorio"],
            "removed_categories": [],
        }
    ]
    with pytest.raises(ValueError, match="items"):
        validate_membership_audit_approval(changed, approved)


def test_membership_apply_approval_rejects_incomplete_fresh_coverage():
    approved = {
        "coverage_verified": True,
        "items": [],
    }
    current = {
        "coverage_verified": False,
        "items": [],
    }

    with pytest.raises(ValueError, match="cobertura actual"):
        validate_membership_audit_approval(current, approved)
