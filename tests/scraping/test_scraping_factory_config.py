from services.scraping.scraping_config import ScrapingConfig


def test_factory_passes_transport_config_to_browser(monkeypatch):
    import services.scraping.scraping_factory as factory_module

    captured = {}

    class FakeDB:
        pass

    class FakeBrowser:
        def __init__(self, session=None, request_timeout=None, max_retries=None):
            captured["session"] = session
            captured["request_timeout"] = request_timeout
            captured["max_retries"] = max_retries

    monkeypatch.setattr(factory_module, "DBManager", FakeDB)
    monkeypatch.setattr(factory_module, "Browser", FakeBrowser)

    config = ScrapingConfig(
        request_timeout=27,
        max_retries=5,
        download_images=False,
    )

    runner = factory_module.ScrapingFactory.create_runner(config)

    assert captured == {
        "session": None,
        "request_timeout": 27,
        "max_retries": 5,
    }
    assert runner.config is config
