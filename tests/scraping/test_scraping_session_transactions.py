from services.scraping.scraping_session import ScrapingSession


class FakeDB:
    def __init__(self):
        self.operations = []

    def begin(self):
        self.operations.append("begin")

    def commit(self):
        self.operations.append("commit")

    def rollback(self):
        self.operations.append("rollback")


class FakeHistoryRepository:
    def __init__(self, db):
        self.db = db
        self.saved = []

    def save(self, history, changes, products):
        self.saved.append((history, changes, products))
        return 17


class FailingRunner:
    def run(self, categories, progress_callback=None):
        raise RuntimeError("fallo controlado")


def test_scraping_session_rolls_back_catalog_and_saves_error_history_cleanly():
    db = FakeDB()
    history_repository = FakeHistoryRepository(db)
    session = ScrapingSession(
        FailingRunner(),
        history_repository=history_repository,
    )

    result = session.execute(categories=[])

    assert result.status() == "ERROR"
    assert result.errors == ["fallo controlado"]
    assert result.history_id == 17
    assert len(history_repository.saved) == 1
    assert db.operations == ["begin", "rollback", "begin", "commit"]
