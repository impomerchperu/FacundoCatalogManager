from scrapers.sync.sync_result import SyncResult


def test_sync_result_initial_values():

    result = SyncResult()

    assert result.new == []

    assert result.updated == []

    assert result.unchanged == []

    assert result.images_processed == 0

    assert result.image_errors == 0

    assert result.errors == []


def test_sync_result_counts():

    result = SyncResult()

    result.new.append(
        "NEW001"
    )

    result.updated.extend(
        [
            "UP001",
            "UP002",
        ]
    )

    result.unchanged.append(
        "SAME001"
    )


    assert result.new_count == 1

    assert result.updated_count == 2

    assert result.unchanged_count == 1


def test_sync_result_summary():

    result = SyncResult()

    result.images_processed = 3

    result.image_errors = 1

    result.errors.append(
        "image failed"
    )


    summary = result.summary()


    assert summary["images_processed"] == 3

    assert summary["image_errors"] == 1

    assert summary["errors"] == 1
