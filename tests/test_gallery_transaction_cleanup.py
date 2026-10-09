from models.scraping.sync_result import SyncResult
from services.scraping.catalog_sync_service import CatalogSyncService


class ActiveDB:
    _transaction_active = True


class Repository:
    db = ActiveDB()


def test_full_catalog_defers_image_cleanup_until_outer_transaction_commits(monkeypatch):
    cleanup_calls = []
    result = SyncResult(
        products_expected=1,
        products_found=1,
        products_unique=1,
    )
    service = CatalogSyncService(
        Repository(),
        object(),
        image_cleanup=lambda: cleanup_calls.append("cleanup") or [],
    )
    monkeypatch.setattr(service, "sync", lambda *args, **kwargs: result)

    returned = service.sync_full_catalog(
        [object()],
        prune_missing=True,
        expected_products=1,
    )

    assert returned is result
    assert cleanup_calls == []
    assert service._deferred_image_cleanup is True

    service.finalize_post_commit()

    assert cleanup_calls == ["cleanup"]
    assert service._deferred_image_cleanup is False
