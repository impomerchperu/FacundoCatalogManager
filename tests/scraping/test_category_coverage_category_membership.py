from types import SimpleNamespace

from models.scraping.category import Category
from services.scraping.category_product_sync_service import CategoryProductSyncService


def _service():
    return CategoryProductSyncService(
        scraper_service=SimpleNamespace(),
        persistence_service=SimpleNamespace(),
    )


def test_category_coverage_does_not_use_substring_matching():
    service = _service()
    service._attach_category_coverage(
        [SimpleNamespace(code="P001", category="Mesa auxiliar de cocina")],
        [],
        [Category("Mesa auxiliar", "https://example.com/mesa", expected_count=1)],
    )

    row = service.last_sync_result.category_summary[0]
    assert row["products"] == 0
    assert row["unique_products"] == 0
    assert row["gap"] == 1


def test_category_coverage_keeps_multi_category_membership():
    service = _service()
    service._attach_category_coverage(
        [
            SimpleNamespace(
                code="P001",
                category="Promocionales, Cocina, Mesa y Hogar",
            )
        ],
        [],
        [
            Category("Promocionales", "https://example.com/p", expected_count=1),
            Category(
                "Cocina, Mesa y Hogar",
                "https://example.com/c",
                expected_count=1,
            ),
        ],
    )

    rows = service.last_sync_result.category_summary
    assert [(row["category"], row["products"]) for row in rows] == [
        ("Promocionales", 1),
        ("Cocina, Mesa y Hogar", 1),
    ]
    assert service.last_sync_result.products_multiple_categories == 0
