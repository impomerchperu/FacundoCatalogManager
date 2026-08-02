import re

import requests

URL = "https://stock.importacionesfacundo.com/producto/jarro-mug-ecologico-con-tapa-600-ml/"


html = requests.get(URL).text


print("=" * 80)
print("BUSCANDO ENDPOINTS AJAX")
print("=" * 80)


patterns = [
    r'wc-ajax=[^"\']+',
    r'admin-ajax\.php[^"\']*',
    r"ajax_[a-zA-Z0-9_]+",
    r'action["\']?\s*[:=]\s*["\']([^"\']+)',
    r'endpoint["\']?\s*[:=]\s*["\']([^"\']+)',
]


found = set()


for pattern in patterns:
    results = re.findall(pattern, html)

    for r in results:
        found.add(r)


for item in sorted(found):
    print(item)


print()
print("TOTAL:", len(found))
