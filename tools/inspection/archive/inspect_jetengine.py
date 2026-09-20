import json

import requests

BASE = "https://stock.importacionesfacundo.com"


endpoints = [
    "/wp-json/jet-engine/v1/meta",
    "/wp-json/jet-engine/v1/post-types",
    "/wp-json/jet-engine/v1/options",
    "/wp-json/jet-engine/v2/meta",
    "/wp-json/jet-engine/v2/post-types",
]


for ep in endpoints:
    print("=" * 80)
    print(ep)

    r = requests.get(BASE + ep)

    print("STATUS:", r.status_code)

    try:
        data = r.json()
        print(json.dumps(data, indent=2, ensure_ascii=False)[:3000])

    except:
        print(r.text[:1000])
