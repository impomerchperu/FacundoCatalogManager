from models.scraping.sync_result import SyncResult


def test_coverage_uses_category_occurrences_not_unique_target():
    result = SyncResult(
        expected_category_occurrences=5,
        products_found=5,
        products_unique=4,
        products_expected=0,
    )

    assert result.category_occurrence_gap == 0
    assert result.coverage_gap == 0
    assert result.coverage_complete is True


def test_coverage_is_incomplete_when_category_occurrences_are_missing():
    result = SyncResult(
        expected_category_occurrences=5,
        products_found=4,
        products_unique=4,
        products_expected=0,
    )

    assert result.category_occurrence_gap == 1
    assert result.coverage_gap == 1
    assert result.coverage_complete is False


def test_to_dict_keeps_occurrence_and_unique_metrics_separate():
    result = SyncResult(
        expected_category_occurrences=525,
        products_found=362,
        products_unique=357,
        products_multiple_categories=136,
    )

    payload = result.to_dict()

    assert payload["reference_category_occurrences"] == 525
    assert payload["actual_category_occurrences"] == 362
    assert payload["unique_products"] == 357
    assert payload["multi_category_products"] == 136
