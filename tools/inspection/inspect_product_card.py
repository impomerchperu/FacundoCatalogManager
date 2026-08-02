from bs4 import BeautifulSoup

from scrapers.browser import Browser

URL = "https://stock.importacionesfacundo.com/categoria-producto/jarros-mug/"

browser = Browser()
html = browser.fetch(URL)

soup = BeautifulSoup(html, "html.parser")

product = soup.select_one('a[href*="/producto/"]')

node = product

for level in range(12):
    node = node.parent

    print("\n")
    print("=" * 80)
    print(f"PADRE {level}")
    print("=" * 80)

    print("TAG:", node.name)
    print("CLASSES:", node.get("class"))

    text = " ".join(node.stripped_strings)
    print("\nTEXTO:")
    print(text[:1200])

    if "Stock Disponible" in text or "S/" in text:
        print("\nHTML:")
        print(node.prettify()[:10000])
        break