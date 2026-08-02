from bs4 import BeautifulSoup

from models.scraping.scraped_product import ScrapedProduct


class ProductParser:

    def parse(
        self,
        html,
        url="",
        category=""
    ):

        soup = BeautifulSoup(html, "html.parser")

        product = soup.select_one(
            ".jsfb-query--querymovil.jsfb-filterable"
        )

        if not product:
            return None


        code = self.extract_code(product)

        name = self.extract_name(product)

        description = self.extract_description(
            product,
            name
        )

        image = self.extract_image(product)

        prices = self.extract_prices(product)

        stock = self.extract_stock(product)


        return ScrapedProduct(

            source="importacionesfacundo",

            url=url,

            code=code,

            name=name,

            category=category,

            description=description,

            image_url=image,

            price_sample=prices["sample"],

            price_hundred=prices["hundred"],

            price_thousand=prices["thousand"],

            stock=stock
        )


    def extract_code(self, product):

        p = product.find("p")

        return p.get_text(strip=True) if p else ""


    def extract_name(self, product):

        h2 = product.find("h2")

        return h2.get_text(strip=True) if h2 else ""


    def extract_description(
        self,
        product,
        name
    ):

        text = product.get_text("\n")

        lines = [
            x.strip()
            for x in text.splitlines()
            if x.strip()
        ]


        ignore = {
            name,
            "Leer Más"
        }


        result = []


        for line in lines:

            if line not in ignore:

                if (
                    line != self.extract_code(product)
                    and "Precio" not in line
                    and "Stock" not in line
                ):
                    result.append(line)


        return "\n".join(result)



    def extract_image(self, product):

        for img in product.find_all("img"):

            url = (
                img.get("data-src")
                or img.get("src")
            )


            if (
                url
                and "FB-" in url
            ):
                return url


        return ""



    def extract_prices(self, product):

        prices = {

            "sample":0,

            "hundred":0,

            "thousand":0
        }


        for block in product.select(".content-precio"):

            title = block.find("h3")

            value = block.find("h4")


            if not title or not value:
                continue


            number = (
                value.text
                .replace("S/","")
                .replace(",","")
                .strip()
            )


            try:
                number=float(number)

            except:
                number=0



            label=title.text.strip()


            if "Muestra" in label:
                prices["sample"]=number

            elif "Ciento" in label:
                prices["hundred"]=number

            elif "Millar" in label:
                prices["thousand"]=number


        return prices



    def extract_stock(self, product):

        text=product.get_text(" ")

        if "Stock Disponible" in text:
            return 0

        return 0