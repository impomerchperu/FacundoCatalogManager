import json

import requests

url = "https://stock.importacionesfacundo.com/wp-json/wc/pos/v1/catalog"


r = requests.get(url)


print("STATUS:", r.status_code)

try:
    print(json.dumps(r.json(), indent=2, ensure_ascii=False)[:3000])

except:
    print(r.text[:3000])
