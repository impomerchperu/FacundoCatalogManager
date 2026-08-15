import re

import requests

url = "https://stock.importacionesfacundo.com/producto/jarro-mug-ecologico-con-tapa-600-ml/"


html = requests.get(url).text


print("=" * 80)
print("PLUGINS ENCONTRADOS")
print("=" * 80)


plugins = sorted(set(re.findall(r"/wp-content/plugins/([^/]+)/", html)))


for p in plugins:
    print(p)
