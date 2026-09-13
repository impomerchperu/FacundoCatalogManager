import sqlite3
from datetime import datetime, timezone

from database.db_manager import DBManager
from models.scraping.scraping_history import ScrapingHistory
from repositories.scraping.scraping_history_repository import ScrapingHistoryRepository


def _history(finished_at: datetime, status: str = "SUCCESS") -> ScrapingHistory:
    started_at = finished_at.replace(second=max(finished_at.second - 1, 0))
    return ScrapingHistory(
        started_at=started_at,
        finished_at=finished_at,
        products_unique=1,
        processed=1,
        created=1,
        status=status,
        errors=0 if status == "SUCCESS" else 1,
    )


def test_successful_save_persists_application_and_replaces_previous_version(tmp_path):
    db = DBManager(str(tmp_path / "catalog.db"))
    repository = ScrapingHistoryRepository(db)
    first = _history(datetime(2026, 9, 12, 10, 0, tzinfo=timezone.utc))
    second = _history(datetime(2026, 9, 12, 11, 0, tzinfo=timezone.utc))

    first_id = repository.save(first)
    assert repository.get_currently_applied().history_id == first_id
    assert repository.get_by_id(first_id).applied_at == first.finished_at

    second_id = repository.save(second)
    assert repository.get_currently_applied().history_id == second_id
    assert repository.get_by_id(first_id).applied_at is None
    assert repository.get_by_id(second_id).applied_at == second.finished_at
    db.close()


def test_error_save_does_not_replace_currently_applied_version(tmp_path):
    db = DBManager(str(tmp_path / "catalog.db"))
    repository = ScrapingHistoryRepository(db)
    successful = _history(datetime(2026, 9, 12, 12, 0, tzinfo=timezone.utc))
    failed = _history(datetime(2026, 9, 12, 13, 0, tzinfo=timezone.utc), "ERROR")

    success_id = repository.save(successful)
    failed_id = repository.save(failed)

    assert repository.get_currently_applied().history_id == success_id
    assert repository.get_by_id(success_id).applied_at == successful.finished_at
    assert repository.get_by_id(failed_id).applied_at is None
    db.close()


def test_migration_marks_only_latest_successful_history_as_applied(tmp_path):
    db_path = tmp_path / "legacy.db"
    connection = sqlite3.connect(db_path)
    connection.execute(
        """
        CREATE TABLE scraping_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            started_at TEXT NOT NULL,
            finished_at TEXT NOT NULL,
            processed INTEGER DEFAULT 0,
            created INTEGER DEFAULT 0,
            updated INTEGER DEFAULT 0,
            unchanged INTEGER DEFAULT 0,
            errors INTEGER DEFAULT 0,
            status TEXT DEFAULT 'SUCCESS'
        )
        """
    )
    connection.executemany(
        """
        INSERT INTO scraping_history (
            started_at, finished_at, processed, created, status
        ) VALUES (?, ?, ?, ?, ?)
        """,
        [
            (
                "2026-09-12T09:59:59+00:00",
                "2026-09-12T10:00:00+00:00",
                1,
                1,
                "SUCCESS",
            ),
            (
                "2026-09-12T10:59:59+00:00",
                "2026-09-12T11:00:00+00:00",
                1,
                1,
                "ERROR",
            ),
            (
                "2026-09-12T11:59:59+00:00",
                "2026-09-12T12:00:00+00:00",
                1,
                1,
                "SUCCESS",
            ),
        ],
    )
    connection.commit()
    connection.close()

    db = DBManager(str(db_path))
    repository = ScrapingHistoryRepository(db)
    current = repository.get_currently_applied()
    assert current is not None
    assert current.history_id == 3
    assert current.applied_at == datetime(2026, 9, 12, 12, 0, tzinfo=timezone.utc)
    assert repository.get_by_id(1).applied_at is None
    db.close()
