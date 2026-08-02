import requests
from bs4 import BeautifulSoup


URL = "https://stock.importacionesfacundo.com/categoria-producto/jarros-mug"


def clean(text):
    if not text:
        return ""

    return "\n".join(
        line.strip()
        for line in text.splitlines()
        if line.strip()
    )


print("=" * 80)
print("DESCARGANDO")
print("=" * 80)

response = requests.get(URL)

print("STATUS:", response.status_code)


soup = BeautifulSoup(response.text, "html.parser")


products = soup.select(
    ".jsfb-query--querymovil.jsfb-filterable"
)


print("=" * 80)
print("PRODUCTOS")
print("=" * 80)

print(len(products))


product = products[0]


print("=" * 80)
print("ESTRUCTURA TEXTO")
print("=" * 80)


for index, div in enumerate(product.find_all("div")):

    text = clean(div.get_text("\n"))

    if len(text) > 100:

        print("-" * 80)
        print("DIV", index)
        print(text[:500])
