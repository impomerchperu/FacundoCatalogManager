from gui.workers.catalog_bootstrap_worker import CatalogBootstrapWorker


def test_catalog_bootstrap_worker_emits_result_and_closes_database(monkeypatch):
    events = []
    fake_db = type("FakeDB", (), {"close": lambda self: events.append("closed")})()

    class FakeService:
        def __init__(self):
            self.db = fake_db
            self.last_bootstrap_changed = True

        def bootstrap(self):
            events.append("bootstrap")
            return 530

    monkeypatch.setattr(
        "gui.workers.catalog_bootstrap_worker.CatalogBootstrapService",
        FakeService,
    )

    worker = CatalogBootstrapWorker()
    worker.finished.connect(
        lambda count, changed: events.append(("finished", count, changed))
    )
    worker.run()

    assert events == [
        "bootstrap",
        ("finished", 530, True),
        "closed",
    ]


def test_catalog_bootstrap_worker_emits_errors_and_closes_database(monkeypatch):
    events = []
    fake_db = type("FakeDB", (), {"close": lambda self: events.append("closed")})()

    class FakeService:
        def __init__(self):
            self.db = fake_db
            self.last_bootstrap_changed = False

        def bootstrap(self):
            raise RuntimeError("fallo controlado")

    monkeypatch.setattr(
        "gui.workers.catalog_bootstrap_worker.CatalogBootstrapService",
        FakeService,
    )

    worker = CatalogBootstrapWorker()
    worker.error.connect(lambda message: events.append(("error", message)))
    worker.run()

    assert events == [
        ("error", "fallo controlado"),
        "closed",
    ]
