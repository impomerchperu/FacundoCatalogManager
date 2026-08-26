from config.scraping_config import (
    JETSMARTFILTERS_ELEMENT_ID,
    JETSMARTFILTERS_INDEXING_FILTERS,
    JETSMARTFILTERS_SIGNATURE,
)

from .category_scraper import CategoryScraper


def _jet_smart_filters_payload(category_id: int, page: int) -> list[tuple[str, str]]:
    """Build the JSF request with the requested page in every pagination field."""
    return [
        ("action", "jet_smart_filters"),
        ("provider", "bricks-query-loop/querydesk"),
        ("query[_tax_query_product_cat]", str(category_id)),
        ("defaults[post_type][]", "product"),
        ("defaults[orderby][menu_order]", "ASC"),
        ("defaults[posts_per_page]", str(CategoryScraper.PRODUCTS_PER_PAGE)),
        ("defaults[no_results_text]", "No existen productos"),
        ("defaults[disable_query_merge]", "true"),
        ("defaults[is_archive_main_query]", "true"),
        ("defaults[post_status]", "publish"),
        ("defaults[paged]", str(page)),
        ("settings[filtered_post_id]", str(category_id)),
        ("settings[element_id]", JETSMARTFILTERS_ELEMENT_ID),
        ("settings[is_archive_main_query]", "true"),
        ("settings[jsf_signature]", JETSMARTFILTERS_SIGNATURE),
        ("props[page]", str(page)),
        ("paged", str(page)),
        ("indexing_filters[]", JETSMARTFILTERS_INDEXING_FILTERS),
    ]


CategoryScraper._jet_smart_filters_payload = staticmethod(
    _jet_smart_filters_payload
)


def _jsf_category_pages(
    self: CategoryScraper,
    category_url: str,
    category_id: int,
    expected_count: int,
) -> list[str]:
    """Enumerate every page required by this category's own product count."""
    found_posts, max_num_pages, first_html = self._fetch_jsf_page(
        category_url, category_id, 1
    )
    category_total = max(int(expected_count or 0), found_posts)
    required_pages = (
        category_total + self.PRODUCTS_PER_PAGE - 1
    ) // self.PRODUCTS_PER_PAGE
    max_num_pages = max(
        max_num_pages,
        required_pages,
        self._declared_total_pages(first_html),
        self._pagination_max_page(first_html),
    )
    if max_num_pages <= 0:
        return [category_url]
    if not first_html:
        raise RuntimeError(
            "JetSmartFilters no devolvió contenido para "
            f"{category_url} en la página 1."
        )

    pages = [category_url]
    self._cache_category_html(category_url, first_html)
    for page_number in range(2, max_num_pages + 1):
        page_url = self._jsf_page_url(category_url, page_number)
        rendered_html = self._fetch_category_page_html(
            category_url, category_id, page_number, page_url
        )
        if not rendered_html:
            raise RuntimeError(
                "JetSmartFilters no devolvió contenido para "
                f"{category_url} en la página "
                f"{page_number}/{max_num_pages}."
            )
        self._cache_category_html(page_url, rendered_html)
        pages.append(page_url)
        page_found, page_total, _ = self._fetch_jsf_page(
            category_url, category_id, page_number
        )
        max_num_pages = max(
            max_num_pages,
            page_total,
            self._declared_total_pages(rendered_html),
            self._pagination_max_page(rendered_html),
            (
                max(category_total, page_found) + self.PRODUCTS_PER_PAGE - 1
            )
            // self.PRODUCTS_PER_PAGE,
        )

    if len(pages) != max_num_pages:
        raise RuntimeError(
            f"Paginación incompleta para {category_url}: "
            f"{len(pages)}/{max_num_pages} páginas."
        )
    return pages


CategoryScraper._jsf_category_pages = _jsf_category_pages
