class ProductExtractor:

    def extract(self, soup):

        name = ""

        if soup.title:
            name = soup.title.text.strip()


        return {
            "name": name,
            "price": 0.0,
            "image_url": "",
            "description": ""
        }