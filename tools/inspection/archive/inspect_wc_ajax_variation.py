import re

import requests

URL = (
    "https://stock.importacionesfacundo.com/"
    "producto/jarro-mug-ecologico-con-tapa-600-ml/"
)


def separator(title):

    print("=" * 80)
    print(title)
    print("=" * 80)


def inspect():

    session = requests.Session()

    separator("DESCARGANDO")

    response = session.get(URL)

    print("STATUS:", response.status_code)

    html = response.text

    separator("BUSCANDO PRODUCT ID")

    patterns = [
        r'data-product_id="(\d+)"',
        r'name="product_id" value="(\d+)"',
        r'product_id["\']?\s*[:=]\s*["\']?(\d+)',
    ]

    for pattern in patterns:
        result = re.findall(pattern, html)

        if result:
            print("ENCONTRADO:", result)

    separator("BUSCANDO ATRIBUTOS")

    attributes = re.findall(r'name="(attribute_[^"]+)"', html)

    for item in attributes:
        print(item)

    separator("BUSCANDO WC AJAX")

    if "wc_ajax_url" in html:
        print("WC AJAX encontrado")

    separator("FORMULARIOS")

    forms = re.findall(r"<form.*?</form>", html, re.DOTALL)

    for form in forms:
        if "variation" in form:
            print(form[:3000])


if __name__ == "__main__":
    inspect()
