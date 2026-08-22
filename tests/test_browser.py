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
