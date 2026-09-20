import json

import requests

variation_id = 60972

url = (
    "https://stock.importacionesfacundo.com/"
    f"wp-json/wc/store/v1/products/{variation_id}"
)


response = requests.get(url)

print("=" * 80)
print(response.status_code)
print("=" * 80)

data = response.json()

print(json.dumps(data, indent=2, ensure_ascii=False))
