from datetime import datetime, timezone
from types import SimpleNamespace

from database.db_manager import DBManager
from repositories.scraping.scraping_history_repository import ScrapingHistoryRepository
from services.scraping.scraping_session import ScrapingSession


def test_history_save_links_to_current_normalized_scraping_run():
    db = DBManager(":memory:")
    history_repository = ScrapingHistoryRepository(db)

    db.execute_query(
        """
        INSERT INTO scraping_runs (started_at, mode, status, categories_requested)
        VALUES (?, 'directed', 'SUCCESS', 1)
        """,
        ("2026-09-20T00:00:00+00:00",),
    )
    run_id = db.fetch_one(
        "SELECT id FROM scraping_runs ORDER BY id DESC LIMIT 1"
    )["id"]

    runner = SimpleNamespace(
        scraping_service=SimpleNamespace(
            normalized_repository=SimpleNamespace(last_run_id=run_id),
        )
    )
    session = ScrapingSession(runner, history_repository=history_repository)
    session.result.started_at = datetime.now(timezone.utc)
    session.result.finished_at = datetime.now(timezone.utc)

    session._save_history()

    history_id = session.result.history_id
    assert history_id is not None
    relation = db.fetch_one(
        """
        SELECT run_id, history_id
        FROM scraping_run_history
        WHERE run_id=?
        """,
        (run_id,),
    )
    assert relation["run_id"] == run_id
    assert relation["history_id"] == history_id

    db.close()


def test_history_save_keeps_legacy_history_unlinked_without_normalized_run():
    db = DBManager(":memory:")
    history_repository = ScrapingHistoryRepository(db)
    runner = SimpleNamespace(scraping_service=SimpleNamespace())
    session = ScrapingSession(runner, history_repository=history_repository)
    session.result.started_at = datetime.now(timezone.utc)
    session.result.finished_at = datetime.now(timezone.utc)

    session._save_history()

    assert (
        db.fetch_one("SELECT COUNT(*) AS n FROM scraping_run_history")["n"] == 0
    )
    db.close()
