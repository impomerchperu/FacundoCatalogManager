import json
import re

import requests


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
    "bulk",
    "hundred",
    "thousand",
    "precio",
]


def separator(title):

    print("=" * 80)
    print(title)
    print("=" * 80)



def inspect():

    separator("DESCARGANDO")

    html = requests.get(URL).text

    print(
        "HTML:",
        len(html)
    )


    separator("BUSCANDO JSON")


    scripts = re.findall(
        r"<script[^>]*>(.*?)</script>",
        html,
        re.DOTALL
    )


    count = 0


    for script in scripts:

        text = script.strip()


        if len(text) < 20:
            continue


        found = [
            k
            for k in KEYWORDS
            if k.lower() in text.lower()
        ]


        if found:

            count += 1

            print()
            print("-" * 80)

            print(
                "KEYWORDS:",
                found
            )


            print(
                text[:1500]
            )


    separator("TOTAL")

    print(count)



if __name__ == "__main__":
    inspect()