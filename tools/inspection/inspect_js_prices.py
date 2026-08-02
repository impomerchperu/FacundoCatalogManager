import re

import requests
from bs4 import BeautifulSoup


URL = (
    "https://stock.importacionesfacundo.com/"
    "producto/jarro-mug-ecologico-con-tapa-600-ml/"
)


KEYWORDS = [
    "price",
    "regular_price",
    "sale_price",
    "wholesale",
    "b2b",
    "role",
    "discount",
    "tier",
    "bulk",
    "min_qty",
    "quantity",
    "ajax",
    "wc_ajax",
    "variation",
    "product_id",
]


def normalize_url(src):
    if src.startswith("//"):
        return "https:" + src

    if src.startswith("/"):
        return "https://stock.importacionesfacundo.com" + src

    return src


def inspect_text(name, text):

    text_lower = text.lower()

    found = [
        keyword
        for keyword in KEYWORDS
        if keyword in text_lower
    ]

    if not found:
        return

    print("=" * 80)
    print(name)
    print("ENCONTRADO:")
    print(found)

    for keyword in found:
        position = text_lower.find(keyword)

        start = max(0, position - 120)
        end = position + 250

        print("-" * 40)
        print(
            text[start:end]
            .replace("\n", " ")
        )


def main():

    print("=" * 80)
    print("DESCARGANDO HTML")
    print("=" * 80)

    response = requests.get(
        URL,
        timeout=30,
    )

    response.raise_for_status()

    html = response.text

    soup = BeautifulSoup(
        html,
        "html.parser",
    )


    print("=" * 80)
    print("ANALIZANDO HTML")
    print("=" * 80)

    inspect_text(
        "HTML PRINCIPAL",
        html,
    )


    print("=" * 80)
    print("SCRIPTS INLINE")
    print("=" * 80)


    for index, script in enumerate(
        soup.find_all("script")
    ):

        if script.string:

            inspect_text(
                f"SCRIPT INLINE #{index}",
                script.string,
            )


    print("=" * 80)
    print("SCRIPTS EXTERNOS")
    print("=" * 80)


    for script in soup.find_all(
        "script",
        src=True,
    ):

        src = normalize_url(
            script["src"]
        )

        try:

            js = requests.get(
                src,
                timeout=20,
            ).text


            inspect_text(
                src,
                js,
            )


        except Exception as e:

            print(
                "ERROR:",
                src,
                e,
            )


if __name__ == "__main__":
    main()