from types import SimpleNamespace

from models.scraping.sync_result import SyncResult
from services.scraping.full_sync_coverage_policy import (
    demonstrates_complete_coverage,
    has_complete_category_coverage,
)


def test_has_complete_category_coverage_accepts_complete_summary():
    result = SyncResult(
        expected_category_occurrences=534,
        products_found=534,
        products_unique=530,
    )
    result.category_summary = [
        {
            "category": "Grupo A",
            "expected": 267,
            "products": 267,
            "unique_products": 267,
            "gap": 0,
        },
        {
            "category": "Grupo B",
            "expected": 267,
            "products": 267,
            "unique_products": 267,
            "gap": 0,
        },
    ]

    assert has_complete_category_coverage(result) is True


def test_has_complete_category_coverage_rejects_category_gap():
    result = SyncResult(
        expected_category_occurrences=534,
        products_found=534,
        products_unique=530,
    )
    result.category_summary = [
        {
            "category": "Grupo A",
            "expected": 267,
            "products": 266,
            "unique_products": 266,
            "gap": 1,
        },
        {
            "category": "Grupo B",
            "expected": 267,
            "products": 268,
            "unique_products": 268,
            "gap": 0,
        },
    ]

    assert has_complete_category_coverage(result) is False


def test_demonstrates_complete_coverage_accepts_534_occurrences_and_530_unique():
    products = [
        SimpleNamespace(code=f"FB-{index + 1:04d}")
        for index in range(530)
    ]
    products.extend(
        SimpleNamespace(code=code)
        for code in ("FB-0001", "FB-0002", "FB-0003", "FB-0004")
    )
    result = SyncResult(
        expected_category_occurrences=534,
        products_found=534,
        products_unique=530,
    )
    result.category_summary = [
        {
            "category": "Grupo A",
            "expected": 267,
            "products": 267,
            "unique_products": 267,
            "gap": 0,
        },
        {
            "category": "Grupo B",
            "expected": 267,
            "products": 267,
            "unique_products": 267,
            "gap": 0,
        },
    ]

    assert demonstrates_complete_coverage(
        result,
        products,
        expected_products=530,
        expected_category_occurrences=534,
    ) is True


def test_demonstrates_complete_coverage_rejects_missing_code():
    result = SyncResult(
        expected_category_occurrences=1,
        products_found=1,
        products_unique=1,
    )
    result.category_summary = [
        {
            "category": "Categoria",
            "expected": 1,
            "products": 1,
            "unique_products": 1,
            "gap": 0,
        }
    ]

    assert demonstrates_complete_coverage(
        result,
        [SimpleNamespace(code="")],
        expected_products=1,
        expected_category_occurrences=1,
    ) is False
