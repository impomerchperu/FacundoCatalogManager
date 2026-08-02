import json

import requests

BASE_URL = "https://stock.importacionesfacundo.com"


IDS = [60971, 60972, 60973, 60974, 60975]


def inspect(product_id):

    url = f"{BASE_URL}/wp-json/wc/store/v1/products/{product_id}"

    print("=" * 80)
    print(url)
    print("=" * 80)

    response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=30)

    print("STATUS:", response.status_code)

    try:
        data = response.json()

        keys = [
            "id",
            "name",
            "sku",
            "type",
            "parent",
            "prices",
            "stock_status",
            "stock_quantity",
            "variations",
        ]

        for key in keys:
            if key in data:
                print("\n", key)
                print(json.dumps(data[key], indent=4, ensure_ascii=False))

    except Exception:
        print(response.text[:2000])


def main():

    for product_id in IDS:
        inspect(product_id)


if __name__ == "__main__":
    main()
