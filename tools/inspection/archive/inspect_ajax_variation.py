import requests
import json


BASE_URL = "https://stock.importacionesfacundo.com"


PRODUCT_URL = (
    BASE_URL
    + "/producto/jarro-mug-ecologico-con-tapa-600-ml/"
)


def separator(title):
    print("=" * 70)
    print(title)
    print("=" * 70)


def inspect_variation_ajax():

    session = requests.Session()

    separator("DESCARGANDO PRODUCTO")

    response = session.get(PRODUCT_URL)

    print("STATUS:")
    print(response.status_code)


    html = response.text


    separator("BUSCANDO WC AJAX")


    keys = [
        "wc_ajax_url",
        "get_variation",
        "product_variations",
        "variation_id",
        "attribute"
    ]


    for key in keys:

        if key in html:

            print("ENCONTRADO:")
            print(key)


    separator("COOKIES")

    print(session.cookies.get_dict())



if __name__ == "__main__":
    inspect_variation_ajax()