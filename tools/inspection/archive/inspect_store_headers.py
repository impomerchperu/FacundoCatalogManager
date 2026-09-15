import requests

url = "https://stock.importacionesfacundo.com/wp-json/wc/store/v1/products/60971"


session = requests.Session()


response = session.get(url)


print("=" * 80)
print("HEADERS")
print("=" * 80)


for k, v in response.headers.items():
    print(k, ":", v)


print()
print("=" * 80)
print("COOKIES")
print("=" * 80)


for cookie in session.cookies:
    print(cookie)
