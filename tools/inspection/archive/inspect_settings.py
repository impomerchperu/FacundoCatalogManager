import re

import requests

URL = "https://stock.importacionesfacundo.com/categoria-producto/jarros-mug/"


headers = {"User-Agent": ("Mozilla/5.0 Windows")}


html = requests.get(URL, headers=headers).text


print("=" * 60)
print("BUSCANDO JetSmartFilterSettings")
print("=" * 60)


pattern = r"JetSmartFilterSettings\s*=\s*(.*?);"


match = re.search(pattern, html, re.DOTALL)


if match:
    data = match.group(1)

    print(data[:5000])

else:
    print("No encontrado")
