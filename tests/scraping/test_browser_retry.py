from scrapers.browser import Browser


class FakeResponse:
    def __init__(self, text, status_code=200):

        self.text = text
        self.status_code = status_code


class FakeSession:
    def __init__(self):

        self.calls = 0

    def get(self, url, headers=None, timeout=None):

        self.calls += 1

        return FakeResponse("<html>ok</html>")


def test_browser_uses_configuration():

    session = FakeSession()

    browser = Browser(session=session)

    result = browser.fetch("https://example.com")

    assert result == "<html>ok</html>"

    assert session.calls == 1
