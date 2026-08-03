from collections import Counter

import requests
from bs4 import BeautifulSoup

URL = "https://stock.importacionesfacundo.com/categoria-producto/jarros-mug/"


def main():

    html = requests.get(URL, headers={"User-Agent": "Mozilla/5.0"}).text

    soup = BeautifulSoup(html, "html.parser")

    products = soup.select(".jsfb-filterable")

    print("=" * 70)
    print("CLASES QUERY")
    print("=" * 70)

    queries = []

    for p in products:
        classes = p.get("class", [])

        for c in classes:
            if "jsfb-query" in c:
                queries.append(c)

    counter = Counter(queries)

    for item, qty in counter.items():
        print(item, "->", qty)

    print()
    print("=" * 70)
    print("TOTAL")
    print("=" * 70)

    print(len(products))


if __name__ == "__main__":
    main()
