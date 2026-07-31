from models.scraping.category import Category


class CategoryExtractor:
    def extract(self, soup):

        categories = []

        links = soup.select("ul.product-categories a")

        for link in links:
            name = link.text.strip()

            url = link.get("href")

            if name and url:
                categories.append(Category(name=name, url=url))

        return categories
