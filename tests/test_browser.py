from scrapers.browser import Browser


def test_browser_fetch():

    browser = Browser()

    html = browser.fetch("https://example.com")

    assert html is not None
    assert "<html" in html.lower()
