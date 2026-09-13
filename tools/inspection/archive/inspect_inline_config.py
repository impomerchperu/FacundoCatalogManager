import re

import requests

url = "https://stock.importacionesfacundo.com/producto/jarro-mug-ecologico-con-tapa-600-ml/"


html = requests.get(url).text


patterns = [
    "ajax",
    "nonce",
    "jet",
    "price",
    "variation",
    "product",
    "role",
    "customer",
    "wholesale",
    "catalog",
]


print("=" * 80)


for p in patterns:
    print("\nBUSCANDO:", p)

    matches = [m.start() for m in re.finditer(p, html, re.IGNORECASE)]

    print("Encontrados:", len(matches))

    if matches:
        pos = matches[0]

        print(html[max(0, pos - 200) : pos + 500])
