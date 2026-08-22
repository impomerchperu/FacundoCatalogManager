from types import SimpleNamespace

from services.scraping.category_name_normalizer import normalize_category_name
from services.scraping.category_product_sync_service import CategoryProductSyncService


def test_normalize_category_name_handles_accents_and_mojibake():
    assert normalize_category_name("Articulos De Antiestres") == (
        "articulos antiestres"
    )
    assert normalize_category_name("ArtÃculos AntiestrÃ©s") == (
        "articulos antiestres"
    )


def test_category_coverage_uses_normalized_key_but_preserves_display_name():
    service = CategoryProductSyncService(object(), object())
    products = [
        SimpleNamespace(
            code="FB-001",
            name="Producto 1",
            category="ArtÃculos AntiestrÃ©s",
        )
    ]
    categories = [
        SimpleNamespace(
            name="Articulos De Antiestres",
            expected_count=1,
        )
    ]

    service._attach_category_coverage(products, categories)

    assert service.last_sync_result.category_summary == [
        {
            "category": "Articulos De Antiestres",
            "comparison_key": "articulos antiestres",
            "products": 1,
            "unique_products": 1,
        }
    ]
