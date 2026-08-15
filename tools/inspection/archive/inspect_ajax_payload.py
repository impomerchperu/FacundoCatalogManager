import json
import re

import requests

URL = "https://stock.importacionesfacundo.com/categoria-producto/jarros-mug/"


response = requests.get(
    URL, headers={"User-Agent": ("Mozilla/5.0 Windows Chrome")}, timeout=30
)


html = response.text


print("=" * 60)
print("BUSCANDO CONFIGURACION COMPLETA")
print("=" * 60)


match = re.search(r"JetSmartFilterSettings\s*=\s*(\{.*?\});", html, re.DOTALL)


if not match:
    print("No encontrada")
    exit()


data = json.loads(match.group(1))


print()
print("=" * 60)
print("QUERY DESK")
print("=" * 60)


print(json.dumps(data["queries"]["bricks-query-loop"]["querydesk"], indent=4))


print()
print("=" * 60)
print("SETTINGS DESK")
print("=" * 60)


print(json.dumps(data["settings"]["bricks-query-loop"]["querydesk"], indent=4))


print()
print("=" * 60)
print("PROPS DESK")
print("=" * 60)


print(json.dumps(data["props"]["bricks-query-loop"]["querydesk"], indent=4))
