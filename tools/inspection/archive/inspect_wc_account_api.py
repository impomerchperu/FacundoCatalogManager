import json

import requests

BASE = "https://stock.importacionesfacundo.com"


endpoints = [
    "/wp-json/wc/store/v1/customers",
    "/wp-json/wc/store/v1/customer",
    "/wp-json/wc/store/v1/account",
    "/wp-json/wc/store/v1/session",
    "/wp-json/wc/store/v1/cart",
]


for ep in endpoints:
    print("=" * 80)
    print(ep)

    r = requests.get(BASE + ep)

    print("STATUS:", r.status_code)

    try:
        print(json.dumps(r.json(), indent=2, ensure_ascii=False)[:2000])

    except:
        print(r.text[:1000])
