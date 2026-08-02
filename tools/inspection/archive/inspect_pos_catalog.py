import json

import requests

BASE_URL = "https://stock.importacionesfacundo.com"


ENDPOINT = f"{BASE_URL}/wp-json/wc/pos/v1/catalog"


def main():

    print("=" * 80)
    print(ENDPOINT)
    print("=" * 80)

    try:
        response = requests.get(
            ENDPOINT, timeout=30, headers={"User-Agent": "Mozilla/5.0"}
        )

        print("STATUS:", response.status_code)

        print("=" * 80)
        print("HEADERS")
        print("=" * 80)

        for key, value in response.headers.items():
            print(f"{key}: {value}")

        print("=" * 80)
        print("RESPUESTA")
        print("=" * 80)

        try:
            data = response.json()

            print(json.dumps(data, indent=4, ensure_ascii=False)[:10000])

            print("\n")

            if isinstance(data, dict):
                print("=" * 80)
                print("CLAVES PRINCIPALES")
                print("=" * 80)

                for key in data.keys():
                    print("-", key)

            elif isinstance(data, list):
                print("=" * 80)
                print("ELEMENTOS")
                print("=" * 80)

                print("Cantidad:", len(data))

                if data:
                    print(json.dumps(data[0], indent=4, ensure_ascii=False))

        except Exception:
            print(response.text[:10000])

    except Exception as e:
        print("ERROR:")
        print(e)


if __name__ == "__main__":
    main()
