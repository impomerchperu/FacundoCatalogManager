import json

import requests

url = "https://stock.importacionesfacundo.com/wp-json/wp/v2/product/60971"


response = requests.get(url)

print("STATUS:")
print(response.status_code)


data = response.json()


print("=" * 80)
print("CAMPOS DISPONIBLES")
print("=" * 80)

for key in data.keys():
    print(key)


print()
print("=" * 80)
print("META")
print("=" * 80)

print(json.dumps(data.get("meta"), indent=2, ensure_ascii=False))
