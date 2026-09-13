import requests
from bs4 import BeautifulSoup

URL = "https://stock.importacionesfacundo.com/categoria-producto/jarros-mug/"


headers = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120 Safari/537.36")
}


response = requests.get(URL, headers=headers, timeout=20)


soup = BeautifulSoup(response.text, "html.parser")


print("=" * 60)
print("SCRIPTS JAVASCRIPT")
print("=" * 60)


for script in soup.find_all("script", src=True):
    src = script["src"]

    print(src)


print()
print("=" * 60)
print("TEXTOS AJAX / QUERY")
print("=" * 60)


html = response.text.lower()


keywords = [
    "admin-ajax",
    "jet-smart",
    "querydesk",
    "bricks-query-loop",
    "ajaxurl",
    "action",
    "provider",
]


for word in keywords:
    if word in html:
        print("Encontrado:", word)
