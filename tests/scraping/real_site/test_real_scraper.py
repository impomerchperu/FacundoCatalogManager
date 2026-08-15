from scrapers.browser import Browser

url = "https://stock.importacionesfacundo.com/tienda/"

browser = Browser()

html = browser.fetch(url)

print("=" * 80)
print("LONGITUD HTML:", len(html))
print("=" * 80)

print(html[:2000])
