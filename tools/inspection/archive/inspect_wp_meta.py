import json

import requests

url = "https://stock.importacionesfacundo.com/wp-json/wp/v2/product/60971"


r = requests.get(url)


data = r.json()


print("=" * 80)
print("META")
print("=" * 80)


print(json.dumps(data.get("meta"), indent=4, ensure_ascii=False))


print("=" * 80)
print("TODAS LAS CLAVES")
print("=" * 80)


for k in data.keys():
    print(k)
