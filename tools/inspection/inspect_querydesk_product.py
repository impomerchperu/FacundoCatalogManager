import requests
from bs4 import BeautifulSoup

URL = "https://stock.importacionesfacundo.com/categoria-producto/jarros-mug/"


def clean(text):
    if not text:
        return ""

    return " ".join(text.split())


def main():

    print("=" * 70)
    print("DESCARGANDO")
    print("=" * 70)

    html = requests.get(URL, headers={"User-Agent": "Mozilla/5.0"}, timeout=30).text

    soup = BeautifulSoup(html, "html.parser")

    print("HTML:", len(html))

    print("=" * 70)
    print("BUSCANDO QUERY DESK")
    print("=" * 70)

    querydesk = soup.select(".jsfb-query--querydesk")

    print("QUERY DESK ENCONTRADOS:", len(querydesk))

    if not querydesk:
        return

    container = querydesk[0]

    print("=" * 70)
    print("HIJOS FILTERABLE")
    print("=" * 70)

    products = container.select(".jsfb-filterable")

    print("PRODUCTOS HIJO:", len(products))

    print()

    for index, product in enumerate(products[:3], start=1):
        print("=" * 70)
        print("PRODUCTO", index)
        print("=" * 70)

        print("CLASES:")

        print(product.get("class"))

        code = product.select_one("p")

        title = product.select_one("h2")

        print()
        print("CODIGO:", clean(code.get_text()) if code else "NO ENCONTRADO")

        print("NOMBRE:", clean(title.get_text()) if title else "NO ENCONTRADO")

        print()

        prices = product.select(".content-precio h4")

        print("PRECIOS:", len(prices))

        for price in prices:
            print(clean(price.get_text()))

        print()


if __name__ == "__main__":
    main()
