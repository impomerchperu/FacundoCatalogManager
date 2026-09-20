import json

import requests

BASE = "https://stock.importacionesfacundo.com"


urls = ["/wp-json/wp/v2/product/60971", "/wp-json/wc/store/v1/products/60971"]


keywords = [
    "price",
    "precio",
    "mayor",
    "ciento",
    "millar",
    "wholesale",
    "venta",
    "compra",
    "cost",
    "regular",
    "muestra",
]


for endpoint in urls:
    print("=" * 80)
    print(endpoint)
    print("=" * 80)

    response = requests.get(BASE + endpoint)

    print("STATUS:", response.status_code)

    data = response.json()

    text = json.dumps(data, ensure_ascii=False, indent=2).lower()

    found = []

    for keyword in keywords:
        if keyword in text:
            found.append(keyword)

    print("PALABRAS ENCONTRADAS:")
    print(found)

    print()
