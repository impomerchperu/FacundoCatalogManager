import requests

url = (
    "https://stock.importacionesfacundo.com/"
    "producto/jarro-mug-ecologico-con-tapa-600-ml/"
)


html = requests.get(url).text


keywords = [
    "FB-1800",
    "1800",
    "precio",
    "price",
    "regular_price",
    "wholesale",
    "mayoreo",
    "ciento",
    "millar",
    "100",
    "1000",
]


print("=" * 80)
print("BUSCANDO DATOS DE PRECIO")
print("=" * 80)


for keyword in keywords:
    print("\nKEYWORD:", keyword)

    if keyword.lower() in html.lower():
        index = html.lower().find(keyword.lower())

        print(html[max(0, index - 300) : index + 500])

    else:
        print("NO ENCONTRADO")
