import json

import requests

BASE = "https://stock.importacionesfacundo.com"

PRODUCT_ID = 60971


urls = [
    f"{BASE}/wp-json/wc/v3/products/{PRODUCT_ID}",
    f"{BASE}/wp-json/wc/v3/products/{PRODUCT_ID}/variations",
]


for url in urls:
    print("=" * 80)
    print(url)
    print("=" * 80)

    response = requests.get(url)

    print("STATUS:", response.status_code)

    try:
        data = response.json()

        print(json.dumps(data, indent=2, ensure_ascii=False)[:5000])

    except Exception:
        print(response.text[:2000])
