from models.scraping.sync_result import SyncResult


def test_coverage_is_complete_when_category_occurrences_are_met():
    result = SyncResult(
        expected_category_occurrences=5,
        products_found=5,
        products_unique=4,
        products_expected=5,
    )

    assert result.category_occurrence_gap == 0
    assert result.coverage_gap == 0
    assert result.coverage_complete is True


def test_unique_count_does_not_override_complete_category_coverage():
    result = SyncResult(
        expected_category_occurrences=5,
        products_found=5,
        products_unique=4,
        products_expected=999,
    )

    assert result.category_occurrence_gap == 0
    assert result.coverage_gap == 0
    assert result.coverage_complete is True


def test_coverage_is_incomplete_when_category_occurrences_are_missing():
    result = SyncResult(
        expected_category_occurrences=5,
        products_found=4,
        products_unique=4,
        products_expected=4,
    )

    assert result.category_occurrence_gap == 1
    assert result.coverage_gap == 1
    assert result.coverage_complete is False


def test_coverage_is_complete_without_category_expectation_when_products_exist():
    result = SyncResult(
        expected_category_occurrences=0,
        products_found=1,
        products_unique=1,
        products_expected=1,
    )

    assert result.coverage_complete is True


def test_to_dict_keeps_occurrence_and_unique_metrics_separate():
    result = SyncResult(
        expected_category_occurrences=20,
        products_found=17,
        products_unique=15,
        products_multiple_categories=2,
    )

    payload = result.to_dict()

    assert payload["reference_category_occurrences"] == 20
    assert payload["actual_category_occurrences"] == 17
    assert payload["unique_products"] == 15
    assert payload["multi_category_products"] == 2


def test_finish_fails_when_category_coverage_is_incomplete():
    result = SyncResult(
        expected_category_occurrences=20,
        products_found=17,
        products_unique=15,
        updated=10,
        unchanged=5,
    )

    result.finish()

    assert result.coverage_complete is False
    assert result.success is False


def test_finish_succeeds_when_category_coverage_is_complete():
    result = SyncResult(
        expected_category_occurrences=20,
        products_found=20,
        products_unique=18,
        unchanged=18,
    )

    result.finish()

    assert result.coverage_complete is True
    assert result.success is True
