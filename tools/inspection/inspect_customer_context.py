import json

import requests

base = "https://stock.importacionesfacundo.com/wp-json/wc/store/v1"


for endpoint in ["/cart", "/products/60971"]:
    print("=" * 80)
    print(endpoint)
    print("=" * 80)

    r = requests.get(base + endpoint)

    print("STATUS:", r.status_code)

    print(json.dumps(r.json(), indent=2, ensure_ascii=False)[:3000])
