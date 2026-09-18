import requests
from bs4 import BeautifulSoup

URL = "https://stock.importacionesfacundo.com/categoria-producto/jarros-mug/"


def clean(text):
    return " ".join(text.split()) if text else ""


def main():

    print("=" * 80)
    print("DESCARGANDO CATEGORIA")
    print("=" * 80)

    response = requests.get(URL, headers={"User-Agent": "Mozilla/5.0"})

    print("STATUS:", response.status_code)
    print("HTML:", len(response.text))

    soup = BeautifulSoup(response.text, "html.parser")

    print("=" * 80)
    print("BUSCANDO BLOQUES PRODUCTO")
    print("=" * 80)

    products = soup.select(".jsfb-filterable")

    print("PRODUCTOS ENCONTRADOS:", len(products))

    if not products:
        print("NO SE ENCONTRARON PRODUCTOS")
        return

    product = products[0]

    print("=" * 80)
    print("PRIMER PRODUCTO")
    print("=" * 80)

    print(product.get_text("\n", strip=True)[:3000])

    print("=" * 80)
    print("IMAGENES")
    print("=" * 80)

    for img in product.find_all("img"):
        print(img.get("src"))

    print("=" * 80)
    print("HTML DEL PRODUCTO")
    print("=" * 80)

    print(product.prettify()[:5000])


if __name__ == "__main__":
    main()
