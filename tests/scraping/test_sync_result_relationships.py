from models.scraping.sync_result import SyncResult


def test_product_category_relationships_count_unique_pairs_not_unique_products():
    result = SyncResult(
        expected_category_occurrences=3,
        products_found=3,
        products_unique=2,
        category_summary=[
            {
                "category": "Categoría A",
                "expected": 2,
                "products": 2,
                "unique_products": 2,
                "gap": 0,
            },
            {
                "category": "Categoría B",
                "expected": 1,
                "products": 1,
                "unique_products": 1,
                "gap": 0,
            },
        ],
    )

    assert result.expected_product_category_relationships == 3
    assert result.product_category_relationships == 3
    assert result.product_category_relationship_gap == 0


def test_product_category_relationships_do_not_count_duplicate_codes_within_category():
    result = SyncResult(
        expected_category_occurrences=2,
        products_found=3,
        products_unique=2,
        category_summary=[
            {
                "category": "Categoría A",
                "expected": 2,
                "products": 3,
                "unique_products": 2,
                "gap": 0,
            },
        ],
    )

    assert result.expected_product_category_relationships == 2
    assert result.product_category_relationships == 2
    assert result.product_category_relationship_gap == 0
