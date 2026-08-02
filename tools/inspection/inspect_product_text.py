from scrapers.browser import Browser
from scrapers.parser import Parser


URL = (
    "https://stock.importacionesfacundo.com/"
    "producto/jarro-mug-ecologico-con-tapa-600-ml/"
)


browser = Browser()

html = browser.fetch(URL)


print("=" * 80)
print("LONGITUD HTML")
print("=" * 80)

print(len(html))


keywords = [
    "S/",
    "precio",
    "ciento",
    "millar",
    "mayorista",
    "venta",
    "unidad",
    "FB-1800"
]


print("=" * 80)
print("COINCIDENCIAS")
print("=" * 80)


for word in keywords:

    print("\nWORD:", word)

    count = html.lower().count(
        word.lower()
    )

    print("COUNT:", count)


    if count:
        pos = html.lower().find(
            word.lower()
        )

        print(
            html[
                max(0,pos-200):
                pos+500
            ]
        )