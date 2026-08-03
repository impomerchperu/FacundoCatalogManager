from bs4 import BeautifulSoup

from scrapers.extractors.product_extractor import ProductExtractor

html = """
<h3 class="brxe-heading">
Jarro Mug Panda
</h3>

<span class="sku">
JAR001
</span>

<div class="posted_in">
<a>Jarros Mug</a>
</div>

<div class="woocommerce-Tabs-panel--description">
Producto de prueba
</div>

<img class="woocommerce-product-gallery"
src="imagen.jpg">
"""


soup = BeautifulSoup(html, "html.parser")


extractor = ProductExtractor()

product = extractor.extract(soup, url="https://test.com/producto")


print(product)
