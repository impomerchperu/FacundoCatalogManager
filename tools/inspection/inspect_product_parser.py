import requests
from bs4 import BeautifulSoup

from scrapers.parser.product_parser import ProductParser

URL = "https://stock.importacionesfacundo.com/categoria-producto/jarros-mug"


print("=" * 80)
print("DESCARGANDO")
print("=" * 80)


response = requests.get(URL)


print("STATUS:", response.status_code)


soup = BeautifulSoup(response.text, "html.parser")


products = soup.select(".jsfb-query--querymovil.jsfb-filterable")


print("=" * 80)
print("PRODUCTOS ENCONTRADOS")
print("=" * 80)

print(len(products))


if not products:
    exit()


# tomamos el primer producto

html_producto = str(products[0])


parser = ProductParser()


product = parser.parse(html_producto)


print("=" * 80)
print("RESULTADO")
print("=" * 80)


print("Código:", product.code)


print("Nombre:", product.name)


print("Imagen:", product.image_url)


print("=" * 80)
print("PRECIOS")
print("=" * 80)


print("Muestra:", product.price_sample)


print("Ciento:", product.price_hundred)


print("Millar:", product.price_thousand)


print("=" * 80)
print("STOCK")
print("=" * 80)


print(product.stock)


print("=" * 80)
print("DESCRIPCIÓN")
print("=" * 80)


print(product.description)
