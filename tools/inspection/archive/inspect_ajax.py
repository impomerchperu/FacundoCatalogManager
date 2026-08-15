import requests

URL = (
    "https://stock.importacionesfacundo.com/"
    "wp-content/plugins/jet-smart-filters/assets/js/public.js?ver=3.5.5"
)


response = requests.get(URL)


print("=" * 60)
print("LONGITUD")
print("=" * 60)

print(len(response.text))


print()
print("=" * 60)
print("FRAGMENTOS AJAX")
print("=" * 60)


text = response.text


keywords = [
    "admin-ajax",
    "action",
    "provider",
    "query_id",
    "queryId",
    "jet_smart_filters",
]


for word in keywords:
    print()
    print("BUSCANDO:", word)

    pos = text.find(word)

    if pos != -1:
        print(text[pos - 200 : pos + 500])
