from types import SimpleNamespace

from models.scraping.sync_result import SyncResult
from services.scraping.scraping_session import ScrapingSession


def test_session_keeps_category_occurrences_after_catalog_consolidation():
    occurrence_result = SyncResult(
        processed=525,
        unchanged=525,
        expected_category_occurrences=529,
        products_found=529,
        products_unique=525,
        products_multiple_categories=4,
        duplicate_occurrences=4,
    )
    catalog_result = SyncResult(
        processed=525,
        unchanged=525,
        expected_category_occurrences=529,
        products_found=525,
        products_unique=525,
        products_multiple_categories=4,
        duplicate_occurrences=0,
    )
    runner = SimpleNamespace(
        scraping_service=SimpleNamespace(
            last_sync_result=occurrence_result,
            catalog_sync_service=SimpleNamespace(last_sync_result=catalog_result),
        )
    )

    session = ScrapingSession(runner)
    session._extract_sync_result()

    assert session.result.products_found == 529
    assert session.result.products_unique == 525
    assert session.result.products_multiple_categories == 4
    assert session.result.duplicate_occurrences == 4
    assert session.result.errors == []


def test_session_falls_back_to_catalog_result_without_occurrence_metrics():
    sync_result = SyncResult(
        processed=10,
        unchanged=10,
        products_expected=10,
        products_found=10,
        products_unique=10,
    )
    catalog_result = SyncResult(
        products_expected=10,
        expected_category_occurrences=10,
        products_found=10,
        products_unique=10,
    )
    runner = SimpleNamespace(
        scraping_service=SimpleNamespace(
            last_sync_result=sync_result,
            catalog_sync_service=SimpleNamespace(last_sync_result=catalog_result),
        )
    )

    session = ScrapingSession(runner)
    session._extract_sync_result()

    assert session.result.products_found == 10
    assert session.result.products_unique == 10
    assert session.result.errors == []
