from models.scraping.sync_result import SyncResult
from services.scraping.category_product_sync_service import CategoryProductSyncService


def test_accumulate_sync_result_does_not_double_count_expectations():
    service = CategoryProductSyncService.__new__(CategoryProductSyncService)
    service.last_sync_result = SyncResult()
    service.last_sync_result.expected_category_occurrences = 61

    result = SyncResult()
    result.expected_category_occurrences = 61
    result.products_found = 61
    result.products_unique = 61
    result.unchanged = 61

    service._accumulate_sync_result(result)

    assert service.last_sync_result.expected_category_occurrences == 61
    assert service.last_sync_result.products_found == 61
    assert service.last_sync_result.products_unique == 61
    assert service.last_sync_result.unchanged == 61
    assert service.last_sync_result.coverage_complete is True
