from types import SimpleNamespace

from services.scraping.scraping_session import ScrapingSession


def _runner_with_coverage(*, coverage_complete: bool):
    sync_result = SimpleNamespace(
        processed=1,
        created=0,
        updated=0,
        unchanged=1,
        deleted=0,
        generated=0,
        changes=[],
        errors=[],
    )
    coverage_result = SimpleNamespace(
        products_expected=1,
        products_found=1 if coverage_complete else 0,
        products_unique=1 if coverage_complete else 0,
        products_multiple_categories=0,
        duplicate_occurrences=0,
        category_summary=[],
        multiple_category_products=[],
        coverage_complete=coverage_complete,
        expected_category_occurrences=1,
        category_occurrence_gap=0 if coverage_complete else 1,
    )
    scraping_service = SimpleNamespace(
        last_sync_result=sync_result,
        catalog_sync_service=SimpleNamespace(last_sync_result=coverage_result),
    )
    return SimpleNamespace(
        scraping_service=scraping_service,
        run=lambda categories, progress_callback=None: [],
    )


def test_session_fails_when_catalog_coverage_is_incomplete():
    session = ScrapingSession(_runner_with_coverage(coverage_complete=False))

    result = session.execute(categories=[])

    assert result.success() is False
    assert result.status() == "ERROR"
    assert result.products_expected == 1
    assert result.products_found == 0
    assert result.errors == [
        "Cobertura del catálogo incompleta: esperados=1, encontrados=0, brecha=1."
    ]


def test_session_succeeds_when_catalog_coverage_is_complete():
    session = ScrapingSession(_runner_with_coverage(coverage_complete=True))

    result = session.execute(categories=[])

    assert result.success() is True
    assert result.status() == "SUCCESS"
    assert result.errors == []
