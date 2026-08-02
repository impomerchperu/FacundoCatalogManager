from scrapers.browser import Browser
from scrapers.parser import Parser

browser = Browser()
parser = Parser()

html = browser.get("https://stock.importacionesfacundo.com/tienda/")

soup = parser.parse(html)

print("=" * 80)

for a in soup.find_all("a", href=True):
    href = a["href"]

    if "/categoria-producto/" in href:
        print(a.get_text(strip=True))
        print(href)
        print("-" * 40)
