import requests

BASE_URL = "https://stock.importacionesfacundo.com"

ENDPOINT = f"{BASE_URL}/wp-json/wc/pos/v1/catalog/create"


def main():

    print("=" * 80)
    print(ENDPOINT)
    print("=" * 80)

    payload = {
        "force": True,
        "_product_fields": (
            "id,name,sku,type,status,price,regular_price,"
            "stock_quantity,images,categories"
        ),
        "_variation_fields": (
            "id,parent,sku,price,regular_price,stock_quantity,attributes"
        ),
    }

    try:
        response = requests.post(
            ENDPOINT,
            json=payload,
            timeout=60,
            headers={"User-Agent": "Mozilla/5.0", "Content-Type": "application/json"},
        )

        print("STATUS:", response.status_code)

        print("=" * 80)
        print(response.text[:15000])

    except Exception as e:
        print("ERROR:")
        print(e)


if __name__ == "__main__":
    main()
