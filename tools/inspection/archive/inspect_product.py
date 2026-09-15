from scrapers.product_scraper import ProductScraper

URL = "https://stock.importacionesfacundo.com/producto/jarro-mug-450-ml/"


def print_section(title):
    print("=" * 80)
    print(title)
    print("=" * 80)


scraper = ProductScraper()

soup = scraper.scrape(URL)


# --------------------------------------------------
# TÍTULO
# --------------------------------------------------

print_section("TÍTULO")

title = soup.select_one("h3.brxe-heading")

if title:
    print(title.get_text(strip=True))
else:
    print("No encontrado")


# --------------------------------------------------
# SKU
# --------------------------------------------------

print_section("SKU")

sku = soup.select_one("span.sku")

if sku:
    print(sku.get_text(strip=True))
else:
    print("No encontrado")


# --------------------------------------------------
# STOCK
# --------------------------------------------------

print_section("STOCK")

stock = soup.select_one(".stock")

if stock:
    print(stock)
else:
    print("No encontrado")


# --------------------------------------------------
# PRECIO
# --------------------------------------------------

print_section("PRECIOS")

price_selectors = [
    ".price",
    ".woocommerce-Price-amount",
    "[class*='price']",
    "[class*='precio']",
]

found_price = False

for selector in price_selectors:
    elements = soup.select(selector)

    if elements:
        print("\nSELECTOR:", selector)

        for element in elements:
            print(element)

        found_price = True


if not found_price:
    print("No encontrado")


# --------------------------------------------------
# DESCRIPCIÓN
# --------------------------------------------------

print_section("DESCRIPCIÓN")


description_selectors = [
    ".x-tabs_panel-content .brxe-text",
    ".brxe-text",
    ".woocommerce-Tabs-panel",
    ".woocommerce-product-details__short-description",
    "[class*='description']",
]


found_description = False


for selector in description_selectors:
    elements = soup.select(selector)

    if elements:
        print("\nSELECTOR:", selector)

        for element in elements:
            text = element.get_text("\n", strip=True)

            if text:
                print(text)

        found_description = True


if not found_description:
    print("No encontrada")


# --------------------------------------------------
# CATEGORÍA
# --------------------------------------------------

print_section("CATEGORÍA")


category_selectors = [
    ".product_meta a[href*='/categoria-producto/']",
    ".posted_in a",
]


for selector in category_selectors:
    elements = soup.select(selector)

    if elements:
        print("SELECTOR:", selector)

        for element in elements:
            print(element.get_text(strip=True))


# --------------------------------------------------
# IMÁGENES
# --------------------------------------------------

print_section("IMÁGENES")


images = soup.select(".woocommerce-product-gallery img")


if images:
    for image in images:
        print(image.get("src"))

else:
    print("No encontradas")


# --------------------------------------------------
# BLOQUES BRICKS / TABS
# --------------------------------------------------

print_section("BLOQUES BRICKS ENCONTRADOS")


for element in soup.select("[class*='brxe']"):
    classes = element.get("class", [])

    if any(
        word in " ".join(classes).lower()
        for word in ["text", "tab", "description", "panel"]
    ):
        text = element.get_text(" ", strip=True)

        if text:
            print(classes, "=>", text[:200])
