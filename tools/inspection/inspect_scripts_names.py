import re

import requests

url = "https://stock.importacionesfacundo.com/producto/jarro-mug-ecologico-con-tapa-600-ml/"


html = requests.get(url).text


scripts = re.findall(r'<script[^>]+src="([^"]+)"', html)


for s in scripts:
    print(s)
