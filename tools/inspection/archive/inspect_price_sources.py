import re

import requests

BASE = "https://stock.importacionesfacundo.com"


urls = [
    "/producto/jarro-mug-ecologico-con-tapa-600-ml/",
    "/wp-json/wc/store/v1/products/60971",
    "/wp-json/wc/store/v1/products/60972",
]


keywords = [
    "precio",
    "price",
    "regular",
    "sale",
    "mayor",
    "ciento",
    "millar",
    "wholesale",
    "role",
    "customer",
    "user",
]


for url in urls:
    print("=" * 80)
    print(BASE + url)

    r = requests.get(BASE + url)

    print("STATUS:", r.status_code)

    text = r.text.lower()

    for key in keywords:
        matches = [m.start() for m in re.finditer(key, text)]

        if matches:
            print(key, "->", len(matches), "encontrados")

            pos = matches[0]

            print(text[max(0, pos - 150) : pos + 250])
