from bs4 import BeautifulSoup

from scrapers.browser import Browser

url = "https://stock.importacionesfacundo.com/categoria-producto/jarros-mug/"


browser = Browser()

html = browser.fetch(url)


soup = BeautifulSoup(html, "html.parser")


cards = soup.select(".jsfb-filterable")


for card in cards:
    link = card.select_one("a[href*='/producto/']")

    if link:
        print("=" * 80)

        print("PRODUCTO:", link.get("href"))

        print("=" * 80)

        images = card.find_all("img")

        for img in images:
            print("IMG:", img.get("src"))

            print("DATA:", img.get("data-src"))

            print()

        break
