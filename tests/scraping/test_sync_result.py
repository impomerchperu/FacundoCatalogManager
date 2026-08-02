from services.scraping.sync_result import SyncResult


def test_sync_result_initial_values():

    result = SyncResult()

    data = result.to_dict()

    assert data["created"] == 0
    assert data["updated"] == 0
    assert data["unchanged"] == 0
    assert data["errors"] == 0


def test_sync_result_increment():

    result = SyncResult()

    result.created += 1
    result.updated += 2

    data = result.to_dict()

    assert data["created"] == 1
    assert data["updated"] == 2
