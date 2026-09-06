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


def test_factory_passes_configured_image_folder_to_downloader(monkeypatch):
    import services.scraping.scraping_factory as factory_module

    captured = {}

    class FakeDB:
        pass

    class FakeBrowser:
        def __init__(self, session=None, request_timeout=None, max_retries=None):
            pass

    class FakeImageDownloader:
        def __init__(self, output_dir, request_timeout, max_retries):
            captured["output_dir"] = output_dir
            captured["request_timeout"] = request_timeout
            captured["max_retries"] = max_retries

    class FakeImageManager:
        def __init__(self, downloader):
            captured["downloader"] = downloader

    class FakeImageSync:
        def __init__(self, image_manager):
            captured["image_manager"] = image_manager

    class FakeImageSyncAdapter:
        def __init__(self, image_sync=None, **kwargs):
            captured["image_sync"] = image_sync

    monkeypatch.setattr(factory_module, "DBManager", FakeDB)
    monkeypatch.setattr(factory_module, "Browser", FakeBrowser)
    monkeypatch.setattr(factory_module, "ImageDownloader", FakeImageDownloader)
    monkeypatch.setattr(factory_module, "SafeImageManager", FakeImageManager)
    monkeypatch.setattr(factory_module, "ImageSync", FakeImageSync)
    monkeypatch.setattr(factory_module, "ImageSyncAdapter", FakeImageSyncAdapter)

    config = ScrapingConfig(
        images_folder="data/custom-images",
        request_timeout=7,
        max_retries=4,
    )

    factory_module.ScrapingFactory.create_runner(config)

    assert captured["output_dir"].as_posix() == "data/custom-images/products"
    assert captured["request_timeout"] == 7
    assert captured["max_retries"] == 4
