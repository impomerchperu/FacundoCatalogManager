import re

import requests

url = "https://stock.importacionesfacundo.com/producto/jarro-mug-ecologico-con-tapa-600-ml/"


html = requests.get(url).text


keywords = [
    "FB-1800",
    "60971",
    "60972",
    "meta",
    "variation",
    "ajax",
    "wc_ajax",
    "product_id",
    "custom",
    "field",
    "price",
    "regular",
    "sale",
    "wholesale",
    "role",
    "user",
    "stock",
]


for key in keywords:
    print("=" * 80)
    print("BUSCANDO:", key)

    results = [m.start() for m in re.finditer(key, html, re.IGNORECASE)]

    print("Encontrados:", len(results))

    for pos in results[:3]:
        print(html[pos - 150 : pos + 300].replace("\n", " "))
