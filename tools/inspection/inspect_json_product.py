import json
import re

import requests
from bs4 import BeautifulSoup


URL = (
    "https://stock.importacionesfacundo.com/"
    "producto/jarro-mug-ecologico-con-tapa-600-ml/"
)


def separator(title):
    print("=" * 80)
    print(title)
    print("=" * 80)


def inspect_variations():

    separator("DESCARGANDO HTML")

    html = requests.get(URL).text

    print("HTML:", len(html))


    separator("BUSCANDO PRODUCT_VARIATIONS")


    patterns = [
        r'data-product_variations="(.*?)"',
        r'"product_variations":(.*?])',
    ]


    variations = None


    for pattern in patterns:

        match = re.search(
            pattern,
            html,
            re.DOTALL
        )

        if match:

            print("ENCONTRADO")

            data = match.group(1)

            data = (
                data
                .replace("&quot;", '"')
                .replace("\\/", "/")
            )


            try:

                variations = json.loads(data)

            except Exception as e:

                print("ERROR JSON")
                print(e)


            break



    if not variations:

        print("NO HAY VARIACIONES")

        return


    separator("VARIACIONES")


    print(
        "TOTAL:",
        len(variations)
    )


    for item in variations:

        print("-" * 60)

        print(
            json.dumps(
                item,
                indent=4,
                ensure_ascii=False
            )
        )



if __name__ == "__main__":

    inspect_variations()