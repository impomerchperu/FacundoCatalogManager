import requests

url = (
    "https://stock.importacionesfacundo.com/wp-json/wc/v3/products/custom-fields/names"
)


r = requests.get(url)


print("STATUS:", r.status_code)

print(r.text[:3000])
