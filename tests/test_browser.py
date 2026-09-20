from config.scraping_config import JETSMARTFILTERS_AJAX_URL
from scrapers.browser import Browser


class FakeResponse:
    def __init__(self, text):
        self.text = text

    def raise_for_status(self):
        return None


class FakeSession:
    def __init__(self):
        self.get_calls = []
        self.post_calls = []

    def get(self, url, headers=None, timeout=None):
        self.get_calls.append((url, headers, timeout))
        return FakeResponse("<html>fixture</html>")

    def post(self, url, data=None, headers=None, timeout=None):
        self.post_calls.append((url, data, headers, timeout))
        return FakeResponse('{"found_posts": 50, "max_num_pages": 2}')


def test_browser_fetch_uses_session_without_network():
    session = FakeSession()
    browser = Browser(session=session)

    html = browser.fetch("https://example.test/catalog")

    assert html == "<html>fixture</html>"
    assert len(session.get_calls) == 1
    metrics = browser.get_http_metrics()
    assert metrics["http_requests"] == 1
    assert metrics["http_successes"] == 1
    assert metrics["category_http_requests"] == 0
    assert metrics["other_http_requests"] == 1
    assert metrics["other_semaphore_wait_count"] == 1
    assert metrics["other_semaphore_wait_seconds"] >= 0.0
    assert metrics["http_max_in_flight_by_class"]["other"] == 1
    assert metrics["http_latency_percentiles"]["other"]["p50"] >= 0.0
    assert metrics["http_latency_percentiles"]["other"]["p95"] >= 0.0


def test_browser_post_uses_metrics_pipeline():
    session = FakeSession()
    browser = Browser(session=session)

    result = browser.post(
        "https://example.test/wp-admin/admin-ajax.php",
        data={"paged": "1"},
    )

    assert result == '{"found_posts": 50, "max_num_pages": 2}'
    assert len(session.post_calls) == 1
    metrics = browser.get_http_metrics()
    assert metrics["http_requests"] == 1
    assert metrics["http_successes"] == 1
    assert metrics["other_http_requests"] == 1
    assert metrics["http_errors"] == 0
    assert metrics["other_semaphore_wait_count"] == 1
    assert metrics["other_semaphore_wait_seconds"] >= 0.0


def test_browser_classifies_jetsmartfilters_ajax_separately():
    session = FakeSession()
    browser = Browser(session=session)

    browser.post(
        JETSMARTFILTERS_AJAX_URL,
        data={"paged": "2"},
    )

    metrics = browser.get_http_metrics()
    assert metrics["http_requests"] == 1
    assert metrics["jsf_http_requests"] == 1
    assert metrics["jsf_http_total_seconds"] >= 0.0
    assert metrics["jsf_http_max_seconds"] >= 0.0
    assert metrics["jsf_semaphore_wait_count"] == 1
    assert metrics["http_max_in_flight_by_class"]["jsf"] == 1
    assert metrics["http_latency_percentiles"]["jsf"]["p50"] >= 0.0
    assert metrics["http_latency_percentiles"]["jsf"]["p95"] >= 0.0
    assert metrics["jsf_semaphore_wait_seconds"] >= 0.0
    assert metrics["other_http_requests"] == 0
    assert metrics["retry_events"] == []


def test_browser_close_closes_owned_http_sessions_once(monkeypatch):
    created_sessions = []

    class RecordingSession:
        def __init__(self):
            self.close_calls = 0
            created_sessions.append(self)

        def close(self):
            self.close_calls += 1

    monkeypatch.setattr(
        "scrapers.browser.requests.Session",
        RecordingSession,
    )

    browser = Browser()
    browser.enable_thread_sessions()
    browser._get_session()

    assert len(created_sessions) == 2

    browser.close()
    browser.close()

    assert [session.close_calls for session in created_sessions] == [1, 1]
