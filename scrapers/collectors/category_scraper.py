        if not html:
            return []
        soup = self._parse(html)
        if self.category_extractor:
            return self.category_extractor.extract(soup)
        return []

    def get_category_pages(self, category_url: str, expected_count: int = 0) -> list[str]:
        category_html = self.get_html(category_url)
        if not category_html:
            return []
        category_id = self._category_id(category_html)
        if category_id is not None and self._is_facundo_url(category_url):
            return self._jsf_category_pages(category_url, category_id, expected_count)
        return self._fallback_category_pages(category_url, category_html, expected_count)

    def _jsf_category_pages(self, category_url: str, category_id: int, expected_count: int) -> list[str]:
        _, max_num_pages, first_html = self._fetch_jsf_page(category_url, category_id, 1)
        expected_pages = self._required_page_count(expected_count)
        max_num_pages = max(
            max_num_pages,
            expected_pages,
            self._declared_total_pages(first_html),
            self._pagination_max_page(first_html),
        )
        if max_num_pages <= 0:
            return [category_url]

        pages = [category_url]
        if first_html:
            self._cache_category_html(category_url, first_html)
        for page_number in range(2, max_num_pages + 1):
            page_url = self._jsf_page_url(category_url, page_number)
            _, _, rendered_html = self._fetch_jsf_page(category_url, category_id, page_number)
            if rendered_html:
                self._cache_category_html(page_url, rendered_html)
            pages.append(page_url)
        return pages

    def _fetch_category_page_html(self, category_url: str, category_id: int, page: int, page_url: str) -> str:
        if self._is_facundo_url(category_url):
            _, _, rendered_html = self._fetch_jsf_page(category_url, category_id, page)
            return rendered_html
        try:
            html = self.get_html(page_url)
        except requests.RequestException:
            html = ""
        if html and self._product_keys(html):
            return html
        _, _, rendered_html = self._fetch_jsf_page(category_url, category_id, page)
        return rendered_html or html