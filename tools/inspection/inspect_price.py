import requests
from bs4 import BeautifulSoup
import re


URL = (
    "https://stock.importacionesfacundo.com/"
    "producto/taza-de-plastico/"
)


KEYWORDS = [
    "precio",
    "price",
    "sample",
    "ciento",
    "millar",
    "mayor",
    "wholesale",
    "bulk",
    "quantity",
    "threshold",
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


    soup = BeautifulSoup(
        html,
        "html.parser"
    )


    separator("TEXTOS CON PALABRAS CLAVE")


    text = soup.get_text(
        " ",
        strip=True
    )


    for keyword in KEYWORDS:

        if keyword.lower() in text.lower():

            print(
                "ENCONTRADO:",
                keyword
            )


    separator("DATA ATTRIBUTES")


    tags = soup.find_all(True)


    for tag in tags:

        attrs = str(tag.attrs).lower()

        found = [
            k
            for k in KEYWORDS
            if k in attrs
        ]

        if found:

            print("-" * 60)

            print(found)

            print(tag.attrs)



    separator("SCRIPTS INLINE")


    for script in soup.find_all("script"):

        content = script.text.lower()

        found = [
            k
            for k in KEYWORDS
            if k in content
        ]

        if found:

            print("-" * 60)

            print(found)

            print(
                script.text[:2000]
            )



if __name__ == "__main__":

    inspect()