import requests
from bs4 import BeautifulSoup

URL = "https://stock.importacionesfacundo.com/categoria-producto/jarros-mug"


def clean(text):
    if not text:
        return ""
    return " ".join(text.split())


print("=" * 80)
print("DESCARGANDO CATEGORIA")
print("=" * 80)

response = requests.get(URL)

print("STATUS:", response.status_code)
print("HTML:", len(response.text))


soup = BeautifulSoup(response.text, "html.parser")


print("=" * 80)
print("BUSCANDO PRODUCTO MOVIL")
print("=" * 80)


products = soup.select(".jsfb-query--querymovil.jsfb-filterable")


print("PRODUCTOS:", len(products))


if not products:
    print("NO ENCONTRADOS")
    exit()


product = products[0]


print("=" * 80)
print("CODIGO")
print("=" * 80)


code = product.find("p")

print(clean(code.get_text()) if code else "NO")


print("=" * 80)
print("NOMBRE")
print("=" * 80)


name = product.find("h2")

print(clean(name.get_text()) if name else "NO")


print("=" * 80)
print("IMAGENES")
print("=" * 80)


for img in product.find_all("img"):
    url = img.get("data-src") or img.get("src")

    if url and not url.startswith("data:image"):
        print(url)


print("=" * 80)
print("PRECIOS")
print("=" * 80)


prices = product.select(".content-precio")


print("Bloques precio:", len(prices))


for price in prices:
    title = price.find("h3")
    value = price.find("h4")

    if title and value:
        print(clean(title.text), "=>", clean(value.text))


print("=" * 80)
print("STOCK")
print("=" * 80)


text = product.get_text("\n")


for line in text.splitlines():
    if "Stock" in line:
        print(clean(line))
