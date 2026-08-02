import requests

url = "https://stock.importacionesfacundo.com/wp-json/"


r = requests.get(url)

data = r.json()


print("=" * 80)
print("RUTAS RELACIONADAS")
print("=" * 80)


for route in data.get("routes", {}):
    if any(x in route.lower() for x in ["jet", "meta", "product", "wc", "woo"]):
        print(route)
