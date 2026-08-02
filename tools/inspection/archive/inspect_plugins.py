import json

import requests

url = "https://stock.importacionesfacundo.com/wp-json/wp/v2/plugins"


r = requests.get(url)


print("=" * 80)
print("STATUS")
print("=" * 80)

print(r.status_code)


print("=" * 80)
print("RESPUESTA")
print("=" * 80)


try:
    print(json.dumps(r.json(), indent=2, ensure_ascii=False))

except:
    print(r.text[:3000])
