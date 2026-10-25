from services.scraping.image_sync_adapter import (
    ImageSyncAdapter,
)


def test_image_sync_adapter_processes_products():

    class FakeImageSync:

        def __init__(self):
            self.called = False

        def process(self, products):

            self.called = True

            return products


    image_sync = FakeImageSync()

    adapter = ImageSyncAdapter(
        image_sync=image_sync,
    )

    products = [
        {
            "code": "P001",
            "image_url": "image.jpg",
        }
    ]

    result = adapter.sync_products(
        products,
    )

    assert image_sync.called is True

    assert result == products

def test_image_sync_adapter_logs_gallery_source_cache_metrics(monkeypatch):
    import services.scraping.image_sync_adapter as module

    log_lines = []
    monkeypatch.setattr(
        module,
        "_log_timing",
        lambda message, *args: log_lines.append(message % args),
    )

    before_metrics = {
        "fresh_hits": 1,
        "network_validations": 2,
        "not_modified_304": 0,
        "updated_200": 2,
        "stale_fallbacks": 0,
        "empty_response_fallbacks": 0,
        "request_errors": 0,
    }
    after_metrics = {
        "fresh_hits": 5,
        "network_validations": 3,
        "not_modified_304": 1,
        "updated_200": 3,
        "stale_fallbacks": 1,
        "empty_response_fallbacks": 0,
        "request_errors": 1,
    }

    class FakeBrowser:
        def __init__(self):
            self.cache_calls = 0

        def get_http_metrics(self):
            return {}

        def get_source_page_cache_metrics(self):
            self.cache_calls += 1
            return before_metrics if self.cache_calls == 1 else after_metrics

    class FakeImageSync:
        def process(self, products):
            return products

    class FakeGallerySync:
        def __init__(self):
            self.browser = FakeBrowser()
            self.refresh_existing = True

        def sync_products(self, products, progress_callback=None):
            return products

    adapter = module.ImageSyncAdapter(
        image_sync=FakeImageSync(),
        gallery_sync=FakeGallerySync(),
    )
    adapter.sync_products([{"code": "CACHE-001"}])

    cache_logs = [
        line for line in log_lines if "stage=gallery_source_page_cache" in line
    ]
    assert len(cache_logs) == 1
    assert "fresh_hits=4" in cache_logs[0]
    assert "network_validations=1" in cache_logs[0]
    assert "not_modified_304=1" in cache_logs[0]
    assert "updated_200=1" in cache_logs[0]
    assert "stale_fallbacks=1" in cache_logs[0]
    assert "request_errors=1" in cache_logs[0]
