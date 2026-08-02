from scrapers.browser import Browser


URL = (
    "https://stock.importacionesfacundo.com/"
    "producto/jarro-mug-ecologico-con-tapa-600-ml/"
)


browser = Browser()

html = browser.fetch(URL)


print("=" * 80)
print("BUSCANDO AJAX ACTIONS")
print("=" * 80)


keywords = [
    "action:",
    "ajax",
    "bricks",
    "jet",
    "query",
    "listing",
    "price",
    "product"
]


for keyword in keywords:

    print("\n")
    print("=" * 80)
    print(keyword)
    print("=" * 80)


    start = 0
    count = 0


    while True:

        pos = html.lower().find(
            keyword.lower(),
            start
        )


        if pos == -1:
            break


        print(
            html[
                max(0,pos-150):
                pos+300
            ]
        )


        count += 1

        start = pos + 1


        if count >= 5:
            break