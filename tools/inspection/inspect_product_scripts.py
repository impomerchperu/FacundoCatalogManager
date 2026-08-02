from scrapers.browser import Browser


URL = (
    "https://stock.importacionesfacundo.com/"
    "producto/jarro-mug-ecologico-con-tapa-600-ml/"
)


browser = Browser()

html = browser.fetch(URL)


print("=" * 80)
print("SCRIPTS")
print("=" * 80)


from bs4 import BeautifulSoup


soup = BeautifulSoup(
    html,
    "html.parser"
)


scripts = soup.find_all(
    "script"
)


print(
    "TOTAL SCRIPTS:",
    len(scripts)
)


keywords = [
    "price",
    "precio",
    "FB-1800",
    "60971",
    "variation",
    "ajax",
    "jet",
    "custom"
]


for script in scripts:

    content = script.text


    if not content:
        continue


    found = False


    for word in keywords:

        if word.lower() in content.lower():

            found = True


    if found:

        print("\n")
        print("=" * 80)

        print(
            content[:1500]
        )