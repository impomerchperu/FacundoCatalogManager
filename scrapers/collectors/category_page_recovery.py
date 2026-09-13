"""Canonical recovery of category pages required for coverage."""

from __future__ import annotations

from .category_scraper import CategoryScraper


def recover_missing_category_pages(
    scraper: CategoryScraper,
    category_url: str,
    pages: list[str],
    required_pages: int,
) -> list[str]:
    """Recover pages missing from a category pagination result."""
    if not scraper._is_facundo_url(category_url):
        return pages

    category_html = scraper.get_html(category_url)
    category_id = scraper._category_id(category_html)
    if category_id is None:
        return pages

    recovered = list(pages) or [category_url]
    known = set(recovered)
    for page in range(2, required_pages + 1):
        page_url = scraper._jsf_page_url(category_url, page)
        if page_url in known:
            continue

        rendered_html = scraper._fetch_category_page_html(
            category_url,
            category_id,
            page,
            page_url,
        )
        if not rendered_html:
            raise RuntimeError(
                "No se pudo recuperar la página "
                f"{page}/{required_pages} de la categoría {category_url}."
            )

        scraper._cache_category_html(page_url, rendered_html)
        recovered.append(page_url)
        known.add(page_url)

    return recovered
