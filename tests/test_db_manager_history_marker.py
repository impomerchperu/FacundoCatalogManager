import sqlite3

from database.db_manager import DBManager


def test_restore_applied_history_marker_uses_latest_successful_history():
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.execute(
        """
        CREATE TABLE scraping_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            finished_at TEXT NOT NULL,
            status TEXT NOT NULL,
            applied_at TEXT
        )
        """
    )
    connection.executemany(
        """
        INSERT INTO scraping_history
            (finished_at, status, applied_at)
        VALUES (?, ?, NULL)
        """,
        [
            ("2026-09-13T10:00:00+00:00", "SUCCESS"),
            ("2026-09-13T11:00:00+00:00", "ERROR"),
            ("2026-09-13T12:00:00+00:00", "SUCCESS"),
        ],
    )
    connection.commit()

    manager = DBManager.__new__(DBManager)
    manager.connection = connection
    manager._restore_applied_history_marker()

    rows = connection.execute(
        """
        SELECT id, applied_at
        FROM scraping_history
        ORDER BY id
        """
    ).fetchall()

    assert rows[0]["applied_at"] is None
    assert rows[1]["applied_at"] is None
    assert rows[2]["applied_at"] == "2026-09-13T12:00:00+00:00"
