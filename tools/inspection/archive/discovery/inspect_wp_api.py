import json

import requests

PRODUCT_ID = 60971


URL = f"https://stock.importacionesfacundo.com/wp-json/wp/v2/product/{PRODUCT_ID}"


response = requests.get(URL, headers={"User-Agent": "Mozilla/5.0"}, timeout=20)


print("=" * 80)
print("STATUS")
print("=" * 80)

print(response.status_code)


print("=" * 80)
print("RESPUESTA")
print("=" * 80)


try:
    data = response.json()

    print(json.dumps(data, indent=2, ensure_ascii=False)[:10000])

except Exception:
    print(response.text[:5000])
