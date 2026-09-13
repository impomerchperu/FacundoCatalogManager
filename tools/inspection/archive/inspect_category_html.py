import requests
from bs4 import BeautifulSoup

URL = "https://stock.importacionesfacundo.com/categoria-producto/proximo-ingreso/"


html = requests.get(URL).text


print("=" * 80)
print("LONGITUD HTML")
print("=" * 80)

print(len(html))


soup = BeautifulSoup(html, "html.parser")


print("=" * 80)
print("TEXTOS CON S/")
print("=" * 80)


for tag in soup.find_all(["h3", "h4", "span", "div"]):
    text = tag.get_text(" ", strip=True)

    if "S/" in text:
        print("----------------")
        print(tag.name)
        print(tag.get("class"))
        print(text)
