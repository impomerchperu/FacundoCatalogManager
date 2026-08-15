from collections import Counter

import requests
from bs4 import BeautifulSoup

CATEGORY_URL = "https://stock.importacionesfacundo.com/categoria-producto/jarros-mug/"


def clean_text(value):
    if not value:
        return ""

    return " ".join(value.split())


def main():

    print("=" * 80)
    print("DESCARGANDO CATEGORIA")
    print("=" * 80)

    response = requests.get(
        CATEGORY_URL,
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=30,
    )

    print("STATUS:", response.status_code)
    print("HTML:", len(response.text))

    soup = BeautifulSoup(response.text, "html.parser")

    print("=" * 80)
    print("BUSCANDO BLOQUES")
    print("=" * 80)

    products = soup.select(".jsfb-filterable")

    print("BLOQUES ENCONTRADOS:", len(products))

    codes = []
    names = []
    urls = []

    for product in products:
        code = product.select_one("p")

        if code:
            codes.append(clean_text(code.get_text()))

        title = product.select_one("h2")

        if title:
            names.append(clean_text(title.get_text()))

        link = product.select_one("a[href*='/producto/']")

        if link:
            urls.append(link.get("href"))

    print()
    print("=" * 80)
    print("RESULTADOS")
    print("=" * 80)

    print("CODIGOS:", len(codes))

    print("CODIGOS UNICOS:", len(set(codes)))

    print("NOMBRES:", len(names))

    print("NOMBRES UNICOS:", len(set(names)))

    print("URL PRODUCTOS:", len(urls))

    print("URL UNICAS:", len(set(urls)))

    print()
    print("=" * 80)
    print("DUPLICADOS")
    print("=" * 80)

    duplicated_codes = {
        item: count for item, count in Counter(codes).items() if count > 1
    }

    duplicated_urls = {
        item: count for item, count in Counter(urls).items() if count > 1
    }

    print("CODIGOS DUPLICADOS:")
    print(duplicated_codes if duplicated_codes else "NINGUNO")

    print()
    print("URL DUPLICADAS:")
    print(duplicated_urls if duplicated_urls else "NINGUNA")


if __name__ == "__main__":
    main()
