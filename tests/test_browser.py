from scraper.browser import Browser

browser = Browser()

html = browser.get("https://www.google.com")

print(html[:200])
