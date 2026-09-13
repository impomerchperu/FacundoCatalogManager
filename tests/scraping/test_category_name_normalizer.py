from types import SimpleNamespace

from services.scraping.category_name_normalizer import (
    canonical_category_name,
    merge_category_names,
    normalize_category_name,
    split_category_names,
)
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


def test_canonical_category_name_merges_cocina_variants():
    assert canonical_category_name("Cocina") == "Cocina, Mesa y Hogar"
    assert canonical_category_name("Mesa") == "Cocina, Mesa y Hogar"
    assert canonical_category_name("Hogar") == "Cocina, Mesa y Hogar"
    assert (
        canonical_category_name("Cocina, Mesa y Hogar")
        == "Cocina, Mesa y Hogar"
    )


def test_canonical_category_name_covers_observed_product_variants():
    expected = {
        "Articulos De Antiestres": "Artículos Antiestrés",
        "Articulos antiesres": "Artículos Antiestrés",
        "Articulos De Escritorio": "Artículos de Escritorio",
        "Articulos De Oficina": "Artículos de Oficina",
        "Articulos De Playa": "Artículos de Playa",
        "Articulos Personales": "Artículos Personales",
        "Bolsas Mochilas": "Bolsas / Mochilas",
        "Cocina Mesa Y Hogar": "Cocina, Mesa y Hogar",
        "Enmicadoras Laminadoras": "Enmicadoras / Laminadoras",
        "Impresoras Y Consumible Fotograficas Termicas": (
            "Impresoras y Consumible Fotográficas Térmicas"
        ),
        "Insumos De Sublimacion": "Insumos de Sublimación",
        "Insumos de Sublimaci?n": "Insumos de Sublimación",
        "Lapiceros Metalicos": "Lapiceros Metálicos",
        "Llaveros Y Accesorios": "Llaveros y Accesorios",
        "Maquinas De Sublimacion": "Máquinas de Sublimación",
        "Micas Para Enmicados": "Micas para Enmicados",
        "Papeleria Grafipapel": "Papelería Grafipapel",
        "Papeles Fotograficos Koala Paper": "Papeles Fotográficos",
        "Plotters De Corte": "Plotters de Corte",
        "Porta Tacos Post It": "Porta Tacos Post-It",
        "Tecnologia Y Accesorios": "Tecnologia y Accesorios",
    }

    for raw, canonical in expected.items():
        assert canonical_category_name(raw) == canonical


def test_split_category_names_deduplicates_aliases():
    assert split_category_names(
        "Papeles Fotograficos Koala Paper, Papeles Fotográficos"
    ) == ["Papeles Fotográficos"]
    assert split_category_names(
        "Articulos De Playa, Articulos De Antiestres"
    ) == ["Artículos de Playa", "Artículos Antiestrés"]


def test_split_category_names_does_not_split_canonical_cocina_category():
    assert split_category_names("Cocina, Mesa y Hogar") == [
        "Cocina, Mesa y Hogar"
    ]


def test_merge_category_names_deduplicates_and_preserves_multi_categories():
    assert merge_category_names(
        "Cocina",
        "Cocina, Mesa y Hogar",
        "Artículos de Escritorio",
        "Articulos de Escritorio",
    ) == "Cocina, Mesa y Hogar, Artículos de Escritorio"
