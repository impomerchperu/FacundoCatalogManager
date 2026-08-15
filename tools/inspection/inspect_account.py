import requests
from bs4 import BeautifulSoup

url = "https://stock.importacionesfacundo.com/mi-cuenta/"


r = requests.get(url)


print("=" * 80)
print("STATUS")
print("=" * 80)

print(r.status_code)


soup = BeautifulSoup(r.text, "html.parser")


print("=" * 80)
print("FORMULARIOS")
print("=" * 80)


for form in soup.find_all("form"):
    print(form.get("action"), form.get("method"))


print("=" * 80)
print("PALABRAS CLAVE")
print("=" * 80)


keywords = [
    "login",
    "usuario",
    "password",
    "registr",
    "cliente",
]


html = r.text.lower()


for k in keywords:
    if k in html:
        print("Encontrado:", k)
