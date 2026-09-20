import requests

from scrapers.browser import Browser


class FakeResponse:
    def __init__(self, text="<html>ok</html>", status_code=200):
        self.text = text
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.exceptions.HTTPError(response=self)


class RetrySession:
    def __init__(self, failures=1):
        self.failures = failures
        self.calls = 0

    def get(self, url, headers=None, timeout=None):
        del url, headers, timeout
        self.calls += 1
        if self.calls <= self.failures:
            raise requests.exceptions.Timeout("transient")
        return FakeResponse()


def test_browser_records_retry_backoff_without_changing_retry_policy(monkeypatch):
    session = RetrySession(failures=2)
    sleeps = []
    monkeypatch.setattr("scrapers.browser.time.sleep", sleeps.append)

    browser = Browser(session=session, max_retries=3)

    assert browser.fetch("https://example.test") == "<html>ok</html>"
    assert session.calls == 3
    assert sleeps == [1, 2]

    metrics = browser.get_http_metrics()
    # The existing retry metric counts each attempt after the first,
    # including the successful attempt that completes a retry sequence.
    # Dedicated backoff metrics count the actual sleeps separately.
    assert metrics["http_retries"] == 3
    assert metrics["http_retry_sleep_count"] == 2
    assert metrics["http_retry_sleep_seconds"] == 3.0


def test_browser_resets_retry_backoff_metrics(monkeypatch):
    session = RetrySession(failures=1)
    sleeps = []
    monkeypatch.setattr("scrapers.browser.time.sleep", sleeps.append)

    browser = Browser(session=session, max_retries=2)

    assert browser.fetch("https://example.test") == "<html>ok</html>"
    assert browser.get_http_metrics()["http_retry_sleep_count"] == 1

    browser.reset_http_metrics()
    metrics = browser.get_http_metrics()
    assert metrics["http_retry_sleep_count"] == 0
    assert metrics["http_retry_sleep_seconds"] == 0.0
