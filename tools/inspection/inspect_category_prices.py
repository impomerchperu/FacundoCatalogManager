import requests
from bs4 import BeautifulSoup
import re


URL = (
    "https://stock.importacionesfacundo.com/"
    "categoria-producto/jarros-mug/"
)


print("=" * 80)
print("DESCARGANDO CATEGORIA")
print("=" * 80)


response = requests.get(
    URL,
    timeout=30
)

print("STATUS:", response.status_code)

html = response.text

print("HTML:", len(html))


print("=" * 80)
print("BUSCANDO PRECIOS")
print("=" * 80)


keywords = [
    "content-precio",
    "Precio Muestra",
    "Precio Ciento",
    "Precio Millar",
    "S/",
    "brxe-heading",
]


for keyword in keywords:

    print("\nKEYWORD:")
    print(keyword)

    matches = [
        m.start()
        for m in re.finditer(
            keyword,
            html,
            re.IGNORECASE
        )
    ]

    print("Encontrados:", len(matches))

    for pos in matches[:5]:

        print("-" * 60)

        fragment = html[
            max(0, pos - 250):
            pos + 500
        ]

        print(fragment)


print("=" * 80)
print("ANALIZANDO DOM")
print("=" * 80)


soup = BeautifulSoup(
    html,
    "html.parser"
)


boxes = soup.select(
    ".content-precio"
)


print(
    "Bloques content-precio:",
    len(boxes)
)


for box in boxes[:10]:

    print("-" * 60)

    print(
        box.get_text(
            " ",
            strip=True
        )
    )