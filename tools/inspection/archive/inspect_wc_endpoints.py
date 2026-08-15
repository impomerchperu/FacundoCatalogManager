import requests

BASE_URL = "https://stock.importacionesfacundo.com"


def main():

    url = f"{BASE_URL}/wp-json/"

    print("=" * 80)
    print("CONSULTANDO ENDPOINTS WORDPRESS")
    print("=" * 80)

    response = requests.get(url, timeout=30)

    print("STATUS:")
    print(response.status_code)

    if response.status_code != 200:
        print(response.text)
        return

    data = response.json()

    print("\n" + "=" * 80)
    print("NAMESPACES DISPONIBLES")
    print("=" * 80)

    namespaces = data.get("namespaces", [])

    for namespace in namespaces:
        print(namespace)

    print("\n" + "=" * 80)
    print("BUSCANDO WOOCOMMERCE")
    print("=" * 80)

    for key, value in data.get("routes", {}).items():
        key_lower = key.lower()

        if any(
            word in key_lower
            for word in [
                "price",
                "product",
                "variation",
                "stock",
                "wholesale",
                "bulk",
                "role",
                "customer",
                "wc",
            ]
        ):
            print(key)


if __name__ == "__main__":
    main()
