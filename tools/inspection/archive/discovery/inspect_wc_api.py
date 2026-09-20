import json

import requests

PRODUCT_ID = 60971


BASE = "https://stock.importacionesfacundo.com"


urls = [
    f"{BASE}/wp-json/wc/store/v1/products/{PRODUCT_ID}",
    f"{BASE}/wp-json/wc/store/v1/products/{PRODUCT_ID}/variations",
]


for url in urls:
    print("=" * 80)
    print(url)
    print("=" * 80)

    response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=20)

    print("STATUS:", response.status_code)

    try:
        data = response.json()

        print(json.dumps(data, indent=2, ensure_ascii=False)[:8000])

    except Exception:
        print(response.text[:2000])
