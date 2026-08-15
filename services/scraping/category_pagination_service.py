class CategoryPaginationService:
    def __init__(self, pagination, link_extractor):
        self.pagination = pagination
        self.link_extractor = link_extractor

    def collect_product_links(self, category_url):

        pages = self.pagination.get_pages(category_url)

        links = []

        for page in pages:
            page_links = self.link_extractor.extract(page)

            links.extend(page_links)

        return list(set(links))
